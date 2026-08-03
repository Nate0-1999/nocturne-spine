"""Database boundary for reproducible M2F scorer proposals."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import InjectionEvent
from spine.db.models import ScorerConfig as ScorerConfigRow
from spine.inject.scorer import ScorerConfig as RuntimeScorerConfig
from spine.inject.scorer import ScorerWeights
from spine.learner.contracts import ReplayScoreView, RetrainResponse
from spine.learner.model import (
    FEATURE_NAMES,
    FitSettings,
    LearningExample,
    ReplayScore,
    canonical_digest,
    challenger_score,
    challenger_wins,
    disposition,
    fit_pairwise,
    identity_is_excluded,
    recorded_score,
    split_gates,
)
from spine.tokens import cl100k_token_count

_ADVISORY_LOCK_KEY = 0x4D3246
_ALGORITHM_ID = "m2f-pairwise-squared-hinge-v1"


class LearnerDataError(RuntimeError):
    """The append-only evidence cannot be replayed without guessing."""


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
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def retrain(self) -> RetrainResponse:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}
                )
                configs = (
                    (await session.execute(select(ScorerConfigRow))).scalars().all()
                )
                active_rows = [row for row in configs if row.active]
                if len(active_rows) != 1:
                    raise LearnerDataError(
                        f"expected exactly one active scorer_config row; found {len(active_rows)}"
                    )
                active_row = active_rows[0]
                runtime_configs = {
                    row.version: _runtime_config(row) for row in configs
                }
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
                examples = self._examples(event_rows, runtime_configs)
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
                digest_manifest = {
                    "algorithm": _ALGORITHM_ID,
                    "learner": settings_manifest,
                    "incumbent_weights": active_row.weights,
                    "incumbent_params": active_row.params,
                }
                digest = canonical_digest(
                    incumbent_version=incumbent.version,
                    training=training,
                    holdout=holdout,
                    settings=digest_manifest,
                )
                version = f"m2f-{digest[:16]}"
                proposal_params = deepcopy(active_row.params)
                proposal_params["_learner"] = {
                    "status": "proposed",
                    "algorithm": _ALGORITHM_ID,
                    "source_digest": digest,
                    "source_boundary": max(example.event_uid for example in examples),
                    "training_cutoff": cutoff.isoformat(),
                    "settings": settings_manifest,
                    "fit": {
                        "iterations": fit.iterations,
                        "objective": fit.objective,
                        "training_pairs": fit.pair_count,
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
        configs: Mapping[str, RuntimeScorerConfig],
    ) -> tuple[LearningExample, ...]:
        grouped: dict[UUID, list[InjectionEvent]] = defaultdict(list)
        for row in rows:
            grouped[row.injection_id].append(row)
        excluded = {
            injection_id
            for injection_id, members in grouped.items()
            if any(
                identity_is_excluded(
                    principal_id=member.principal_id,
                    machine_id=member.machine_id,
                )
                for member in members
            )
        }
        passive_discount = Decimal(str(self._settings.passive_discount))
        examples: list[LearningExample] = []
        for row in rows:
            if row.injection_id in excluded:
                continue
            labeled = disposition(
                row.outcome,
                row.actor_class,
                passive_discount=passive_discount,
            )
            if labeled is None:
                continue
            source = configs.get(row.scorer_version)
            if source is None:
                raise LearnerDataError(
                    f"event {row.event_uid} references missing scorer {row.scorer_version!r}"
                )
            features = _features(row)
            baseline_bias = float(row.score) - math.fsum(
                weight * feature
                for weight, feature in zip(_weight_tuple(source.weights), features, strict=True)
            )
            baseline_bias -= source.bias_offset(row.memory_id)
            body = _frozen_body(row)
            target_injected, actor_weight = labeled
            examples.append(
                LearningExample(
                    event_uid=row.event_uid,
                    injection_id=row.injection_id,
                    memory_id=row.memory_id,
                    ts=row.ts,
                    features=features,
                    baseline_bias=baseline_bias,
                    target_injected=target_injected,
                    actor_weight=actor_weight,
                    shown_as=row.shown_as,  # type: ignore[arg-type]
                    body_tokens=cl100k_token_count(body),
                )
            )
        return tuple(examples)


def _runtime_config(row: ScorerConfigRow) -> RuntimeScorerConfig:
    try:
        return RuntimeScorerConfig.from_mappings(
            version=row.version,
            weights=row.weights,
            params=row.params,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise LearnerDataError(f"scorer_config {row.version!r} is invalid") from error


def _features(row: InjectionEvent) -> tuple[float, float, float, float, float, float]:
    values: list[float] = []
    for name in FEATURE_NAMES:
        value = row.features.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LearnerDataError(f"event {row.event_uid} feature {name} is not numeric")
        normalized = float(value)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise LearnerDataError(
                f"event {row.event_uid} feature {name} is outside [0,1]"
            )
        values.append(normalized)
    return tuple(values)  # type: ignore[return-value]


def _frozen_body(row: InjectionEvent) -> str:
    memory = row.features.get("_memory")
    body = memory.get("body") if isinstance(memory, Mapping) else None
    if not isinstance(body, str):
        raise LearnerDataError(f"event {row.event_uid} has no frozen memory body")
    return body


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
