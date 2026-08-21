"""Database boundary for reproducible M2F scorer proposals."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.locking import session_advisory_lock
from spine.db.models import InjectionEvent, InjectionEventAnnotation, LearnerRun
from spine.db.models import ScorerConfig as ScorerConfigRow
from spine.ids import mint_ulid
from spine.inject.scorer import ScorerConfig as RuntimeScorerConfig
from spine.inject.scorer import ScorerWeights
from spine.learner.contracts import ReplayScoreView, RetrainResponse
from spine.learner.evidence import LearnerDataError, project_learning_evidence
from spine.learner.locking import LEARNER_ADVISORY_LOCK_KEY
from spine.learner.model import (
    FEATURE_NAMES,
    FitSettings,
    LearningExample,
    ReplayScore,
    canonical_digest,
    challenger_score,
    challenger_wins,
    fit_pairwise,
    recorded_score,
    split_gates,
)

_ALGORITHM_ID = "m3ti-pairwise-thread-squared-hinge-v2"


@dataclass(frozen=True, slots=True, kw_only=True)
class LearnerSettings:
    min_dispositions: int
    holdout_fraction: float
    passive_discount: float
    pair_margin: float
    bias_l2: float
    win_margin: float

    def manifest(self) -> dict[str, object]:
        return asdict(self)


class LearnerService:
    """Fit challengers from one database snapshot and persist winners inactive."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        settings: LearnerSettings,
        retrain_signal_stride: int = 25,
    ) -> None:
        if retrain_signal_stride <= 0:
            raise ValueError("retrain signal stride must be positive")
        self._session_factory = session_factory
        self._settings = settings
        self._retrain_signal_stride = retrain_signal_stride

    async def retrain(self) -> RetrainResponse:
        """Force the same fit used by background cadence and append its receipt."""

        response = await self._retrain(trigger="manual", due_only=False)
        if response is None:  # pragma: no cover - manual is never a due check
            raise RuntimeError("manual retrain unexpectedly returned no result")
        return response

    async def retrain_if_due(self) -> RetrainResponse | None:
        """Run one background fit only when the durable A-051 cadence is due."""

        return await self._retrain(trigger="background", due_only=True)

    async def _retrain(
        self,
        *,
        trigger: Literal["manual", "background"],
        due_only: bool,
    ) -> RetrainResponse | None:
        async with session_advisory_lock(
            self._session_factory,
            key=LEARNER_ADVISORY_LOCK_KEY,
            name="chrysopoeia",
        ) as connection:
            async with self._session_factory(bind=connection) as session:
                async with session.begin():
                    await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                    return await self._retrain_in_snapshot(
                        session,
                        trigger=trigger,
                        due_only=due_only,
                    )

    async def _retrain_in_snapshot(
        self,
        session: AsyncSession,
        *,
        trigger: Literal["manual", "background"],
        due_only: bool,
    ) -> RetrainResponse | None:
        configs = (await session.execute(select(ScorerConfigRow))).scalars().all()
        active_rows = [row for row in configs if row.active]
        if len(active_rows) != 1:
            raise LearnerDataError(
                f"expected exactly one active scorer_config row; found {len(active_rows)}"
            )
        active_row = active_rows[0]
        runtime_configs = {row.version: _runtime_config(row) for row in configs}
        incumbent = runtime_configs[active_row.version]
        event_rows = (
            (
                await session.execute(
                    select(InjectionEvent).order_by(
                        InjectionEvent.ts,
                        InjectionEvent.injection_id,
                        InjectionEvent.event_uid,
                    )
                )
            )
            .scalars()
            .all()
        )
        annotation_rows = (await session.execute(select(InjectionEventAnnotation))).scalars().all()
        examples = self._examples(event_rows, annotation_rows, runtime_configs)
        if due_only and not await self._background_due(session, len(examples)):
            return None
        response = await self._fit(
            session,
            configs=configs,
            active_row=active_row,
            incumbent=incumbent,
            examples=examples,
        )
        # The mappings intentionally expose no ORM relationship. Persist a
        # winning proposal before its same-transaction receipt satisfies the FK.
        await session.flush()
        source_boundary = max(
            (example.event_uid for example in examples),
            default=None,
        )
        session.add(
            LearnerRun(
                run_uid=mint_ulid(),
                trigger=trigger,
                result=response.status,
                incumbent_version=response.incumbent_version,
                proposal_version=response.proposal_version,
                eligible_dispositions=response.eligible_dispositions,
                training_dispositions=response.training_dispositions,
                holdout_dispositions=response.holdout_dispositions,
                training_pairs=response.training_pairs,
                source_boundary=source_boundary,
                incumbent=(
                    response.incumbent.model_dump() if response.incumbent is not None else None
                ),
                challenger=(
                    response.challenger.model_dump() if response.challenger is not None else None
                ),
                reason=response.reason,
            )
        )
        return response

    async def _background_due(self, session: AsyncSession, eligible: int) -> bool:
        if eligible < self._settings.min_dispositions:
            return False
        cursor = await session.scalar(
            select(LearnerRun)
            .where(LearnerRun.eligible_dispositions >= self._settings.min_dispositions)
            .order_by(
                LearnerRun.eligible_dispositions.desc(),
                LearnerRun.ts.desc(),
                LearnerRun.run_uid.desc(),
            )
            .limit(1)
        )
        if cursor is None:
            return True
        return eligible - cursor.eligible_dispositions >= self._retrain_signal_stride

    async def _fit(
        self,
        session: AsyncSession,
        *,
        configs: list[ScorerConfigRow],
        active_row: ScorerConfigRow,
        incumbent: RuntimeScorerConfig,
        examples: tuple[LearningExample, ...],
    ) -> RetrainResponse:
        prior_challenger_exists = any(
            isinstance(row.params.get("_learner"), Mapping) for row in configs
        )
        if not prior_challenger_exists and len(examples) < self._settings.min_dispositions:
            return _insufficient(
                incumbent.version,
                eligible=len(examples),
                reason=(
                    "minimum disposition floor not reached: "
                    f"{len(examples)}/{self._settings.min_dispositions}"
                ),
            )
        try:
            training, holdout, cutoff = split_gates(
                examples,
                holdout_fraction=self._settings.holdout_fraction,
            )
        except ValueError as error:
            return _insufficient(
                incumbent.version,
                eligible=len(examples),
                reason=str(error),
            )
        try:
            fit = fit_pairwise(
                training,
                incumbent_weights=_weight_tuple(incumbent.weights),
                incumbent_thread_weight=incumbent.params.thread_weight,
                settings=FitSettings(
                    pair_margin=self._settings.pair_margin,
                    bias_l2=self._settings.bias_l2,
                ),
            )
        except ValueError as error:
            return _insufficient(
                incumbent.version,
                eligible=len(examples),
                training=len(training),
                holdout=len(holdout),
                reason=str(error),
            )
        incumbent_score = recorded_score(holdout)
        fitted_score = challenger_score(
            holdout,
            weights=fit.weights,
            bias_offsets=fit.bias_offsets,
            thread_weight=fit.thread_weight,
            tau=incumbent.params.tau,
        )
        wins = challenger_wins(
            incumbent_score,
            fitted_score,
            margin=Decimal(str(self._settings.win_margin)),
        )
        if not wins:
            return RetrainResponse(
                status="not_better",
                incumbent_version=incumbent.version,
                proposal_version=None,
                eligible_dispositions=len(examples),
                training_dispositions=len(training),
                holdout_dispositions=len(holdout),
                training_pairs=fit.pair_count,
                incumbent=_score_view(incumbent_score),
                challenger=_score_view(fitted_score),
                reason="challenger did not clear the replay win rule",
            )
        settings_manifest = self._settings.manifest()
        proposal_params = deepcopy(active_row.params)
        inherited_control = "_control" in proposal_params
        proposal_params.pop("_control", None)
        digest_manifest = {
            "algorithm": _ALGORITHM_ID,
            "learner": settings_manifest,
            "incumbent_weights": active_row.weights,
            "incumbent_params": active_row.params,
        }
        if inherited_control:
            # Pre-fix control-basin proposals inherited _control at the same digest.
            # Version the corrected encoding without erasing incumbent provenance.
            digest_manifest["proposal_encoding"] = "learner_without_control_v1"
        digest = canonical_digest(
            incumbent_version=incumbent.version,
            training=training,
            holdout=holdout,
            settings=digest_manifest,
        )
        version = f"m2f-{digest[:16]}"
        holdout_weight = sum(
            (example.actor_weight for example in holdout),
            start=Decimal(0),
        )
        proposal_params["_learner"] = {
            "status": "proposed",
            "algorithm": _ALGORITHM_ID,
            "source_digest": digest,
            "source_boundary": max(example.event_uid for example in examples),
            "training_cutoff": cutoff.isoformat(),
            "holdout_dispositions": len(holdout),
            "holdout_weight": str(holdout_weight),
            "settings": settings_manifest,
            "fit": {
                "iterations": fit.iterations,
                "objective": fit.objective,
                "training_pairs": fit.pair_count,
                "thread_weight": fit.thread_weight,
            },
            "replay": {
                "incumbent": _score_manifest(incumbent_score),
                "challenger": _score_manifest(fitted_score),
            },
            "bias_offsets": {
                str(memory_id): value
                for memory_id, value in sorted(
                    fit.bias_offsets.items(), key=lambda item: item[0].int
                )
            },
        }
        proposal_weights = dict(zip(FEATURE_NAMES, fit.weights, strict=True))
        if "thread_weight" in proposal_params or fit.thread_weight != 0.0:
            proposal_params["thread_weight"] = fit.thread_weight
        existing = await session.get(ScorerConfigRow, version)
        if existing is None:
            session.add(
                ScorerConfigRow(
                    version=version,
                    weights=proposal_weights,
                    params=proposal_params,
                    active=False,
                )
            )
        elif existing.weights != proposal_weights or existing.params != proposal_params:
            legacy_with_count = deepcopy(proposal_params)
            legacy_learner = legacy_with_count.get("_learner")
            if isinstance(legacy_learner, dict):
                legacy_learner.pop("holdout_weight", None)
            legacy_without_count = deepcopy(legacy_with_count)
            legacy_learner = legacy_without_count.get("_learner")
            if isinstance(legacy_learner, dict):
                legacy_learner.pop("holdout_dispositions", None)
            accepted_params = (legacy_with_count, legacy_without_count)
            if existing.weights != proposal_weights or existing.params not in accepted_params:
                raise LearnerDataError(
                    f"content-addressed scorer proposal {version} does not match stored content"
                )
        return RetrainResponse(
            status="proposed",
            incumbent_version=incumbent.version,
            proposal_version=version,
            eligible_dispositions=len(examples),
            training_dispositions=len(training),
            holdout_dispositions=len(holdout),
            training_pairs=fit.pair_count,
            incumbent=_score_view(incumbent_score),
            challenger=_score_view(fitted_score),
            reason="challenger won replay and remains inactive pending owner activation",
        )

    def _examples(
        self,
        rows: list[InjectionEvent],
        annotations: list[InjectionEventAnnotation],
        configs: Mapping[str, RuntimeScorerConfig],
    ) -> tuple[LearningExample, ...]:
        return project_learning_evidence(
            rows,
            annotations,
            configs,
            passive_discount=Decimal(str(self._settings.passive_discount)),
        ).examples


def _runtime_config(row: ScorerConfigRow) -> RuntimeScorerConfig:
    try:
        return RuntimeScorerConfig.from_mappings(
            version=row.version,
            weights=row.weights,
            params=row.params,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise LearnerDataError(f"scorer_config {row.version!r} is invalid") from error


def _weight_tuple(weights: ScorerWeights) -> tuple[float, float, float, float, float, float]:
    return (weights.sem, weights.kw, weights.time, weights.proj, weights.freq, weights.hist)


def _score_view(score: ReplayScore) -> ReplayScoreView:
    return ReplayScoreView(**_score_manifest(score))


def _score_manifest(score: ReplayScore) -> dict[str, Any]:
    return {
        "disagreements": score.disagreements,
        "weighted_disagreements": str(score.weighted_disagreements),
        "injected_tokens": score.injected_tokens,
    }


def _insufficient(
    incumbent_version: str,
    *,
    eligible: int,
    reason: str,
    training: int = 0,
    holdout: int = 0,
) -> RetrainResponse:
    return RetrainResponse(
        status="insufficient_data",
        incumbent_version=incumbent_version,
        proposal_version=None,
        eligible_dispositions=eligible,
        training_dispositions=training,
        holdout_dispositions=holdout,
        training_pairs=0,
        incumbent=None,
        challenger=None,
        reason=reason,
    )


__all__ = ["LearnerDataError", "LearnerService", "LearnerSettings"]
