"""Database authority for the A-035 Memory Graph and Injection Console."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from spine.contracts import MemoryFeatures, MemoryUnit
from spine.db.models import InjectionEvent
from spine.db.models import MemoryEdge as MemoryEdgeRow
from spine.db.models import MemoryRevision as MemoryRevisionRow
from spine.db.models import MemoryUnit as MemoryUnitRow
from spine.db.models import ScorerActivation as ScorerActivationRow
from spine.db.models import ScorerConfig as ScorerConfigRow
from spine.inject.scorer import ScorerConfig as RuntimeScorerConfig
from spine.learner.model import (
    FEATURE_NAMES,
    LearningExample,
    challenger_score,
    disposition,
    identity_is_excluded,
    split_gates,
)
from spine.m2k.contracts import (
    AccuracyPoint,
    AccuracySlice,
    AccuracySlicePoint,
    ActivateScorerConfigRequest,
    CandidateScoreHistory,
    CandidateScorePoint,
    ContributionBreakdown,
    CreateScorerConfigRequest,
    InstantSimulation,
    MemoryGraphEdge,
    MemoryGraphNode,
    MemoryGraphQuery,
    MemoryGraphSnapshot,
    ParameterRange,
    RevisionTrailItem,
    ScorerActivationView,
    ScorerAuditionRequest,
    ScorerAuditionResponse,
    ScorerComparisonRow,
    ScorerConfigurationView,
    ScorerConsoleQuery,
    ScorerConsoleSnapshot,
    ScorerDescriptor,
    ScorerSimulationRequest,
    ScorerSimulationResponse,
    ScorerValues,
)
from spine.tokens import cl100k_token_count

_CONTROL_LOCK_KEY = 0x4D324B
_CONTROLLED_PARAM_KEYS = (
    "tau",
    "top_k",
    "budget_tokens",
    "half_life_time_days",
    "half_life_hist_days",
)

SCORER_DESCRIPTORS = (
    ScorerDescriptor(
        id="scorer.tau",
        label="Injection threshold",
        type="number",
        range=ParameterRange(minimum=0, maximum=1, step=0.01),
        default=0.55,
    ),
    ScorerDescriptor(
        id="scorer.top_k",
        label="Display limit",
        type="integer",
        range=ParameterRange(minimum=1, maximum=8, step=1),
        default=8,
    ),
    ScorerDescriptor(
        id="scorer.budget_tokens",
        label="Memory token budget",
        type="integer",
        range=ParameterRange(minimum=1, maximum=None, step=128),
        default=3000,
    ),
    ScorerDescriptor(
        id="scorer.half_life_time_days",
        label="Recency half-life (days)",
        type="number",
        range=ParameterRange(minimum=0, maximum=None, step=0.5, exclusive_minimum=True),
        default=14,
    ),
    ScorerDescriptor(
        id="scorer.half_life_hist_days",
        label="Edit-history half-life (days)",
        type="number",
        range=ParameterRange(minimum=0, maximum=None, step=0.5, exclusive_minimum=True),
        default=7,
    ),
    *(
        ScorerDescriptor(
            id=f"scorer.weight.{feature}",
            label=f"{feature.upper()} weight",
            type="number",
            range=ParameterRange(minimum=0, maximum=1, step=0.01),
            default=default,
        )
        for feature, default in zip(
            FEATURE_NAMES, (0.42, 0.16, 0.11, 0.16, 0.08, 0.07), strict=True
        )
    ),
)


class M2KStateError(RuntimeError):
    """The requested graph or scorer operation cannot preserve A-035."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class M2KService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        graph_edge_sim: float,
        holdout_fraction: float = 0.20,
        passive_discount: float = 0.25,
    ) -> None:
        self._session_factory = session_factory
        self._graph_edge_sim = graph_edge_sim
        self._holdout_fraction = holdout_fraction
        self._passive_discount = passive_discount

    async def memory_graph(self, query: MemoryGraphQuery) -> MemoryGraphSnapshot:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                as_of = await _transaction_time(session)
                statement = select(MemoryUnitRow).where(
                    MemoryUnitRow.principal_id == query.principal_id,
                    MemoryUnitRow.status != "candidate",
                )
                if query.memory_ids is not None:
                    statement = statement.where(MemoryUnitRow.id.in_(query.memory_ids))
                rows = (
                    (
                        await session.execute(
                            statement.order_by(MemoryUnitRow.created_at, MemoryUnitRow.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                node_ids = [row.id for row in rows]
                revisions = await _revision_map(session, node_ids)
                edges = await self._graph_edges(session, node_ids, revisions)

        returned = set(node_ids)
        requested = query.memory_ids or []
        return MemoryGraphSnapshot(
            as_of=as_of,
            graph_edge_sim=self._graph_edge_sim,
            nodes=[
                MemoryGraphNode(
                    memory=_memory_unit(row),
                    in_current_context=query.memory_ids is not None,
                    revisions=revisions.get(row.id, []),
                )
                for row in rows
            ],
            edges=edges,
            omitted_memory_ids=[memory_id for memory_id in requested if memory_id not in returned],
        )

    async def _graph_edges(
        self,
        session: AsyncSession,
        node_ids: list[UUID],
        revisions: Mapping[UUID, list[RevisionTrailItem]],
    ) -> list[MemoryGraphEdge]:
        if not node_ids:
            return []
        left = aliased(MemoryUnitRow)
        right = aliased(MemoryUnitRow)
        similarity = (1 - left.embedding.cosine_distance(right.embedding)).label("similarity")
        similarity_rows = (
            await session.execute(
                select(left.id, right.id, similarity)
                .where(
                    left.id.in_(node_ids),
                    right.id.in_(node_ids),
                    left.id < right.id,
                    similarity >= self._graph_edge_sim,
                )
                .order_by(left.id, right.id)
            )
        ).all()
        lineage_rows = (
            (
                await session.execute(
                    select(MemoryEdgeRow)
                    .where(
                        MemoryEdgeRow.from_memory_id.in_(node_ids),
                        MemoryEdgeRow.to_memory_id.in_(node_ids),
                    )
                    .order_by(
                        MemoryEdgeRow.created_at,
                        MemoryEdgeRow.edge_uid,
                    )
                )
            )
            .scalars()
            .all()
        )
        edges = [
            MemoryGraphEdge(
                kind="similarity",
                from_memory_id=from_id,
                to_memory_id=to_id,
                similarity=_decimal_string(sim),
            )
            for from_id, to_id, sim in similarity_rows
        ]
        edges.extend(
            MemoryGraphEdge(
                kind="lineage",
                from_memory_id=row.from_memory_id,
                to_memory_id=row.to_memory_id,
                edge_type=row.edge_type,  # type: ignore[arg-type]
            )
            for row in lineage_rows
        )
        edges.extend(
            MemoryGraphEdge(
                kind="edit_trail",
                from_memory_id=memory_id,
                to_memory_id=memory_id,
                revision_count=len(trail),
            )
            for memory_id, trail in sorted(revisions.items(), key=lambda item: item[0].int)
            if len(trail) > 1
        )
        return edges

    async def scorer_console(self, query: ScorerConsoleQuery) -> ScorerConsoleSnapshot:
        if query.as_of != "now":
            raise M2KStateError("historical_unavailable")
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                as_of = await _transaction_time(session)
                configs = (
                    (
                        await session.execute(
                            select(ScorerConfigRow).order_by(
                                ScorerConfigRow.created_at, ScorerConfigRow.version
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                active = [row for row in configs if row.active]
                if len(active) != 1:
                    raise M2KStateError("invalid_active_scorer")
                activations = (
                    (
                        await session.execute(
                            select(ScorerActivationRow).order_by(
                                ScorerActivationRow.ts,
                                ScorerActivationRow.event_uid,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                event_statement = select(InjectionEvent).where(
                    InjectionEvent.principal_id == query.principal_id
                )
                if query.thread_id is not None:
                    event_statement = event_statement.where(
                        InjectionEvent.thread_id == query.thread_id
                    )
                events = (
                    (
                        await session.execute(
                            event_statement.order_by(InjectionEvent.ts, InjectionEvent.event_uid)
                        )
                    )
                    .scalars()
                    .all()
                )

        config_views = [_config_view(row) for row in configs]
        config_by_version = {row.version: row for row in configs}
        candidates = _candidate_histories(events, config_by_version)
        proposals = [view for view in config_views if view.status == "proposed"]
        return ScorerConsoleSnapshot(
            as_of=as_of,
            scope="CURRENT" if query.thread_id is not None else "GLOBAL",
            thread_id=query.thread_id,
            descriptors=list(SCORER_DESCRIPTORS),
            active_version=active[0].version,
            configurations=config_views,
            activations=[_activation_view(row) for row in activations],
            proposed_versions=proposals,
            accuracy=[_accuracy_point(row) for row in configs],
            candidates=candidates,
        )

    async def create_scorer_config(
        self, body: CreateScorerConfigRequest
    ) -> ScorerConfigurationView:
        target_version = f"m2k-{body.event_uid}"
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": _CONTROL_LOCK_KEY}
                )
                replay = await session.get(ScorerActivationRow, body.event_uid)
                if replay is not None:
                    return await _validate_control_replay(session, replay, target_version, body)
                active = await _active_config(session)
                if active.version != body.base_version:
                    raise M2KStateError("stale_base")
                receipt = await self._deep_receipt(session, active, body.values)
                if receipt.simulation_digest != body.simulation_digest:
                    raise M2KStateError("simulation_stale")
                if await session.get(ScorerConfigRow, target_version) is not None:
                    raise M2KStateError("version_collision")
                params = deepcopy(active.params)
                params.update(
                    {
                        "tau": body.values.tau,
                        "top_k": body.values.top_k,
                        "budget_tokens": body.values.budget_tokens,
                        "half_life_time_days": body.values.half_life_time_days,
                        "half_life_hist_days": body.values.half_life_hist_days,
                    }
                )
                changes = _changes(_values(active), body.values)
                changed_parameter_ids = sorted(changes)
                changes["_force"] = {
                    "simulation_digest": receipt.simulation_digest,
                    "source_boundary": receipt.source_boundary,
                    "holdout_dispositions": receipt.holdout_dispositions,
                    "incumbent_accuracy_percent": receipt.incumbent_accuracy_percent,
                    "accuracy_percent": receipt.accuracy_percent,
                    "delta_percent": receipt.delta_percent,
                }
                params["_control"] = {
                    "event_uid": body.event_uid,
                    "parent_version": active.version,
                    "actor_class": body.actor_class,
                    "machine_id": body.machine_id,
                    "changed_parameter_ids": changed_parameter_ids,
                }
                _validate_runtime_config(target_version, body.values.weights, params)
                active.active = False
                await session.flush()
                target = ScorerConfigRow(
                    version=target_version,
                    weights=dict(body.values.weights),
                    params=params,
                    active=True,
                )
                session.add(target)
                await session.flush()
                session.add(
                    ScorerActivationRow(
                        event_uid=body.event_uid,
                        version=target_version,
                        previous_version=active.version,
                        actor_class=body.actor_class,
                        machine_id=body.machine_id,
                        reason="human_control",
                        changes=changes,
                    )
                )
                await session.flush()
                await session.refresh(target)
                return _config_view(target)

    async def simulate(self, body: ScorerSimulationRequest) -> ScorerSimulationResponse:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                base = await session.get(ScorerConfigRow, body.base_version)
                if base is None or not base.active:
                    raise M2KStateError("stale_base")
                receipt = await self._deep_receipt(session, base, body.values)
                instant = await _instant(
                    session,
                    principal_id=body.principal_id,
                    injection_id=body.injection_id,
                    preview=base,
                    preview_values=body.values,
                )
                slice_view = await self._slice(
                    session,
                    base,
                    body.values,
                    body.slice_parameter_id,
                )
        return receipt.model_copy(update={"instant": instant, "slice": slice_view})

    async def audition(self, body: ScorerAuditionRequest) -> ScorerAuditionResponse:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                incumbent = await _active_config(session)
                proposal = await session.get(ScorerConfigRow, body.proposal_version)
                learner = proposal.params.get("_learner") if proposal is not None else None
                if (
                    proposal is None
                    or proposal.active
                    or not isinstance(learner, Mapping)
                    or learner.get("status") != "proposed"
                ):
                    raise M2KStateError("not_proposed")
                instant = await _instant(
                    session,
                    principal_id=body.principal_id,
                    injection_id=body.injection_id,
                    preview=proposal,
                    preview_values=_values(proposal),
                )
        return ScorerAuditionResponse(
            incumbent_version=incumbent.version,
            proposal_version=proposal.version,
            instant=instant,
        )

    async def _deep_receipt(
        self,
        session: AsyncSession,
        base: ScorerConfigRow,
        values: ScorerValues,
    ) -> ScorerSimulationResponse:
        configs = (await session.execute(select(ScorerConfigRow))).scalars().all()
        config_map = {row.version: _runtime(row) for row in configs}
        rows = (
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
        examples = _examples(
            rows,
            config_map,
            passive_discount=Decimal(str(self._passive_discount)),
            values=values,
        )
        source_boundary = max((item.event_uid for item in examples), default=None)
        holdout: tuple[LearningExample, ...] = ()
        if examples:
            try:
                _, holdout, _ = split_gates(
                    examples,
                    holdout_fraction=self._holdout_fraction,
                )
            except ValueError:
                holdout = ()
        base_runtime = _runtime(base)
        incumbent_values = _values(base)
        incumbent_score = (
            challenger_score(
                _rescale_examples(holdout, rows, config_map, incumbent_values),
                weights=_weight_tuple(incumbent_values),
                bias_offsets=base_runtime.bias_offsets,
                tau=incumbent_values.tau,
            )
            if holdout
            else None
        )
        preview_score = (
            challenger_score(
                holdout,
                weights=_weight_tuple(values),
                bias_offsets=base_runtime.bias_offsets,
                tau=values.tau,
            )
            if holdout
            else None
        )
        incumbent_accuracy = _accuracy(incumbent_score, len(holdout))
        accuracy = _accuracy(preview_score, len(holdout))
        delta = (
            None
            if accuracy is None or incumbent_accuracy is None
            else accuracy - incumbent_accuracy
        )
        digest_payload = {
            "base_version": base.version,
            "values": values.model_dump(mode="json"),
            "source_boundary": source_boundary,
            "holdout_dispositions": len(holdout),
            "incumbent_accuracy_percent": _optional_decimal(incumbent_accuracy),
            "accuracy_percent": _optional_decimal(accuracy),
            "delta_percent": _optional_decimal(delta),
        }
        digest = hashlib.sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return ScorerSimulationResponse(
            simulation_digest=digest,
            base_version=base.version,
            values=values,
            source_boundary=source_boundary,
            holdout_dispositions=len(holdout),
            accuracy_percent=_optional_decimal(accuracy),
            incumbent_accuracy_percent=_optional_decimal(incumbent_accuracy),
            delta_percent=_optional_decimal(delta),
            instant=InstantSimulation(status="not_requested", injection_id=None, candidates=[]),
            slice=AccuracySlice(parameter_id="scorer.tau", points=[]),
        )

    async def _slice(
        self,
        session: AsyncSession,
        base: ScorerConfigRow,
        values: ScorerValues,
        parameter_id: str,
    ) -> AccuracySlice:
        points: list[AccuracySlicePoint] = []
        for value in _slice_values(values, parameter_id):
            candidate = _with_parameter(values, parameter_id, value)
            receipt = await self._deep_receipt(session, base, candidate)
            points.append(
                AccuracySlicePoint(value=value, accuracy_percent=receipt.accuracy_percent)
            )
        return AccuracySlice(parameter_id=parameter_id, points=points)  # type: ignore[arg-type]

    async def activate_proposal(
        self,
        version: str,
        body: ActivateScorerConfigRequest,
    ) -> ScorerConfigurationView:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": _CONTROL_LOCK_KEY}
                )
                replay = await session.get(ScorerActivationRow, body.event_uid)
                if replay is not None:
                    if (
                        replay.version != version
                        or replay.actor_class != body.actor_class
                        or replay.machine_id != body.machine_id
                        or replay.reason != "learner_proposal"
                    ):
                        raise M2KStateError("event_uid_conflict")
                    target = await session.get(ScorerConfigRow, version)
                    if target is None:
                        raise M2KStateError("missing_version")
                    return _config_view(target)
                active = await _active_config(session)
                target = await session.get(ScorerConfigRow, version)
                if target is None:
                    raise M2KStateError("missing_version")
                learner = target.params.get("_learner")
                if (
                    target.active
                    or not isinstance(learner, Mapping)
                    or learner.get("status") != "proposed"
                ):
                    raise M2KStateError("not_proposed")
                changes = _changes(_values(active), _values(target))
                active.active = False
                await session.flush()
                target.active = True
                session.add(
                    ScorerActivationRow(
                        event_uid=body.event_uid,
                        version=target.version,
                        previous_version=active.version,
                        actor_class=body.actor_class,
                        machine_id=body.machine_id,
                        reason="learner_proposal",
                        changes=changes,
                    )
                )
                await session.flush()
                return _config_view(target)


async def _transaction_time(session: AsyncSession) -> datetime:
    value = await session.scalar(select(func.transaction_timestamp()))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RuntimeError("Postgres returned an invalid snapshot timestamp")
    return value


async def _revision_map(
    session: AsyncSession, memory_ids: list[UUID]
) -> dict[UUID, list[RevisionTrailItem]]:
    if not memory_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(MemoryRevisionRow)
                .where(MemoryRevisionRow.memory_id.in_(memory_ids))
                .order_by(
                    MemoryRevisionRow.memory_id,
                    MemoryRevisionRow.ts,
                    MemoryRevisionRow.rev_uid,
                )
            )
        )
        .scalars()
        .all()
    )
    result: dict[UUID, list[RevisionTrailItem]] = defaultdict(list)
    for row in rows:
        result[row.memory_id].append(
            RevisionTrailItem(
                rev_uid=row.rev_uid,
                parent_uid=row.parent_uid,
                revision=row.revision,
                ts=row.ts,
                reason=row.reason,
            )
        )
    return dict(result)


def _memory_unit(row: MemoryUnitRow) -> MemoryUnit:
    return MemoryUnit(
        memory_id=row.id,
        principal_id=row.principal_id,
        label=row.label,
        body=row.body,
        kind=row.kind,  # type: ignore[arg-type]
        keywords=list(row.keywords),
        project_key=row.project_key,
        thread_origin=row.thread_origin,
        origin_path=row.origin_path,
        pin=row.pin,
        status=row.status,  # type: ignore[arg-type]
        revision=row.revision,
        stats=dict(row.stats),
        bias=row.bias,
        embedding_model=row.embedding_model,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _values(row: ScorerConfigRow) -> ScorerValues:
    try:
        return ScorerValues(
            tau=float(row.params["tau"]),
            top_k=int(row.params["top_k"]),
            budget_tokens=int(row.params["budget_tokens"]),
            half_life_time_days=float(row.params["half_life_time_days"]),
            half_life_hist_days=float(row.params["half_life_hist_days"]),
            weights={name: float(row.weights[name]) for name in FEATURE_NAMES},
        )
    except (KeyError, TypeError, ValueError) as error:
        raise M2KStateError(f"invalid_scorer:{row.version}") from error


def _config_view(row: ScorerConfigRow) -> ScorerConfigurationView:
    learner = row.params.get("_learner")
    proposed = (
        isinstance(learner, Mapping)
        and learner.get("status") == "proposed"
        and "_control" not in row.params
    )
    status = "active" if row.active else "proposed" if proposed else "inactive"
    replay = learner.get("replay") if isinstance(learner, Mapping) else None
    return ScorerConfigurationView(
        version=row.version,
        created_at=row.created_at,
        status=status,
        values=_values(row),
        replay=dict(replay) if isinstance(replay, Mapping) else None,
    )


def _activation_view(row: ScorerActivationRow) -> ScorerActivationView:
    return ScorerActivationView(
        event_uid=row.event_uid,
        version=row.version,
        previous_version=row.previous_version,
        actor_class=row.actor_class,  # type: ignore[arg-type]
        machine_id=row.machine_id,
        reason=row.reason,  # type: ignore[arg-type]
        changes=dict(row.changes),
        ts=row.ts,
    )


def _accuracy_point(row: ScorerConfigRow) -> AccuracyPoint:
    learner = row.params.get("_learner")
    replay = learner.get("replay") if isinstance(learner, Mapping) else None
    challenger = replay.get("challenger") if isinstance(replay, Mapping) else None
    holdout = learner.get("holdout_dispositions") if isinstance(learner, Mapping) else None
    disagreements = challenger.get("disagreements") if isinstance(challenger, Mapping) else None
    if (
        isinstance(holdout, int)
        and not isinstance(holdout, bool)
        and holdout > 0
        and isinstance(disagreements, int)
        and not isinstance(disagreements, bool)
        and 0 <= disagreements <= holdout
        and "_control" not in row.params
    ):
        accuracy = Decimal(100) * Decimal(holdout - disagreements) / Decimal(holdout)
        return AccuracyPoint(
            version=row.version,
            created_at=row.created_at,
            status="measured",
            accuracy_percent=_decimal_string(accuracy),
            holdout_dispositions=holdout,
            disagreements=disagreements,
        )
    return AccuracyPoint(
        version=row.version,
        created_at=row.created_at,
        status="not_recorded",
        accuracy_percent=None,
        holdout_dispositions=None,
        disagreements=None,
    )


def _candidate_histories(
    events: list[InjectionEvent],
    configs: Mapping[str, ScorerConfigRow],
) -> list[CandidateScoreHistory]:
    grouped: dict[UUID, list[CandidateScorePoint]] = defaultdict(list)
    identity: dict[UUID, tuple[str, str]] = {}
    for event in events:
        config = configs.get(event.scorer_version)
        if config is None:
            raise M2KStateError(f"missing_event_scorer:{event.scorer_version}")
        frozen = event.features.get("_memory")
        label = frozen.get("label") if isinstance(frozen, Mapping) else ""
        identity[event.memory_id] = (
            label if isinstance(label, str) else "",
            event.memory_kind,
        )
        features = MemoryFeatures(**{name: float(event.features[name]) for name in FEATURE_NAMES})
        contributions = {
            name: Decimal(str(getattr(features, name))) * Decimal(str(config.weights[name]))
            for name in FEATURE_NAMES
        }
        stored_score = Decimal(str(event.score))
        bias = stored_score - sum(contributions.values(), start=Decimal(0))
        grouped[event.memory_id].append(
            CandidateScorePoint(
                event_uid=event.event_uid,
                injection_id=event.injection_id,
                ts=event.ts,
                scorer_version=event.scorer_version,
                score=_decimal_string(stored_score),
                rank=event.rank,
                shown_as=event.shown_as,  # type: ignore[arg-type]
                outcome=event.outcome,
                features=features,
                contributions=ContributionBreakdown(
                    **{
                        **{name: _decimal_string(value) for name, value in contributions.items()},
                        "bias": _decimal_string(bias),
                    }
                ),
            )
        )
    return [
        CandidateScoreHistory(
            memory_id=memory_id,
            label=identity[memory_id][0],
            kind=identity[memory_id][1],
            points=points,
        )
        for memory_id, points in sorted(grouped.items(), key=lambda item: item[0].int)
    ]


def _changes(old: ScorerValues, new: ScorerValues) -> dict[str, Any]:
    old_flat = _flat_values(old)
    new_flat = _flat_values(new)
    return {
        key: {"old": old_flat[key], "new": new_flat[key]}
        for key in old_flat
        if old_flat[key] != new_flat[key]
    }


def _flat_values(values: ScorerValues) -> dict[str, float | int]:
    result: dict[str, float | int] = {
        "scorer.tau": values.tau,
        "scorer.top_k": values.top_k,
        "scorer.budget_tokens": values.budget_tokens,
        "scorer.half_life_time_days": values.half_life_time_days,
        "scorer.half_life_hist_days": values.half_life_hist_days,
    }
    result.update({f"scorer.weight.{name}": value for name, value in values.weights.items()})
    return result


def _validate_runtime_config(
    version: str,
    weights: Mapping[str, float],
    params: Mapping[str, Any],
) -> None:
    try:
        RuntimeScorerConfig.from_mappings(version=version, weights=weights, params=params)
    except (KeyError, TypeError, ValueError) as error:
        raise M2KStateError("invalid_values") from error


def _runtime(row: ScorerConfigRow) -> RuntimeScorerConfig:
    try:
        return RuntimeScorerConfig.from_mappings(
            version=row.version,
            weights=row.weights,
            params=row.params,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise M2KStateError(f"invalid_scorer:{row.version}") from error


def _weight_tuple(values: ScorerValues) -> tuple[float, float, float, float, float, float]:
    return tuple(values.weights[name] for name in FEATURE_NAMES)  # type: ignore[return-value]


def _examples(
    rows: list[InjectionEvent],
    configs: Mapping[str, RuntimeScorerConfig],
    *,
    passive_discount: Decimal,
    values: ScorerValues,
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
    examples: list[LearningExample] = []
    for row in rows:
        if row.injection_id in excluded:
            continue
        labeled = disposition(row.outcome, row.actor_class, passive_discount=passive_discount)
        if labeled is None:
            continue
        source = configs.get(row.scorer_version)
        if source is None:
            raise M2KStateError(f"missing_event_scorer:{row.scorer_version}")
        examples.append(_example(row, source, values, labeled))
    return tuple(examples)


def _example(
    row: InjectionEvent,
    source: RuntimeScorerConfig,
    values: ScorerValues,
    labeled: tuple[bool, Decimal],
) -> LearningExample:
    original = tuple(_feature(row, name) for name in FEATURE_NAMES)
    adjusted = list(original)
    adjusted[2] = _rescale_decay(
        original[2], source.params.half_life_time_days, values.half_life_time_days
    )
    adjusted[5] = _rescale_decay(
        original[5], source.params.half_life_hist_days, values.half_life_hist_days
    )
    baseline_bias = float(row.score) - math.fsum(
        weight * feature
        for weight, feature in zip(
            (
                source.weights.sem,
                source.weights.kw,
                source.weights.time,
                source.weights.proj,
                source.weights.freq,
                source.weights.hist,
            ),
            original,
            strict=True,
        )
    )
    baseline_bias -= source.bias_offset(row.memory_id)
    frozen = row.features.get("_memory")
    body = frozen.get("body") if isinstance(frozen, Mapping) else None
    if not isinstance(body, str):
        raise M2KStateError(f"event_not_replayable:{row.event_uid}")
    target, actor_weight = labeled
    return LearningExample(
        event_uid=row.event_uid,
        injection_id=row.injection_id,
        memory_id=row.memory_id,
        ts=row.ts,
        features=tuple(adjusted),  # type: ignore[arg-type]
        baseline_bias=baseline_bias,
        target_injected=target,
        actor_weight=actor_weight,
        shown_as=row.shown_as,  # type: ignore[arg-type]
        body_tokens=cl100k_token_count(body),
    )


def _rescale_examples(
    examples: tuple[LearningExample, ...],
    rows: list[InjectionEvent],
    configs: Mapping[str, RuntimeScorerConfig],
    values: ScorerValues,
) -> tuple[LearningExample, ...]:
    by_uid = {row.event_uid: row for row in rows}
    result: list[LearningExample] = []
    for existing in examples:
        row = by_uid[existing.event_uid]
        source = configs[row.scorer_version]
        result.append(
            _example(
                row,
                source,
                values,
                (existing.target_injected, existing.actor_weight),
            )
        )
    return tuple(result)


def _feature(row: InjectionEvent, name: str) -> float:
    value = row.features.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M2KStateError(f"invalid_event_feature:{row.event_uid}:{name}")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 <= normalized <= 1:
        raise M2KStateError(f"invalid_event_feature:{row.event_uid}:{name}")
    return normalized


def _rescale_decay(value: float, source_half_life: float, target_half_life: float) -> float:
    return 0.0 if value == 0 else value ** (source_half_life / target_half_life)


def _accuracy(score: Any, count: int) -> Decimal | None:
    if score is None or count == 0:
        return None
    return Decimal(100) * Decimal(count - score.disagreements) / Decimal(count)


def _optional_decimal(value: Decimal | None) -> str | None:
    return None if value is None else _decimal_string(value)


async def _instant(
    session: AsyncSession,
    *,
    principal_id: str,
    injection_id: UUID | None,
    preview: ScorerConfigRow,
    preview_values: ScorerValues,
) -> InstantSimulation:
    if injection_id is None:
        return InstantSimulation(status="not_requested", injection_id=None, candidates=[])
    rows = (
        (
            await session.execute(
                select(InjectionEvent)
                .where(
                    InjectionEvent.injection_id == injection_id,
                    InjectionEvent.principal_id == principal_id,
                )
                .order_by(InjectionEvent.rank, InjectionEvent.event_uid)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise M2KStateError("missing_injection")
    prepare_meta = rows[0].features.get("_prepare")
    context_tokens = (
        prepare_meta.get("model_context_tokens") if isinstance(prepare_meta, Mapping) else None
    )
    if (
        isinstance(context_tokens, bool)
        or not isinstance(context_tokens, int)
        or context_tokens <= 0
    ):
        return InstantSimulation(status="not_replayable", injection_id=injection_id, candidates=[])
    config_rows = (await session.execute(select(ScorerConfigRow))).scalars().all()
    configs = {row.version: _runtime(row) for row in config_rows}
    preview_runtime = _runtime(preview)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        source = configs.get(row.scorer_version)
        if source is None:
            raise M2KStateError(f"missing_event_scorer:{row.scorer_version}")
        original = tuple(_feature(row, name) for name in FEATURE_NAMES)
        adjusted = list(original)
        adjusted[2] = _rescale_decay(
            original[2], source.params.half_life_time_days, preview_values.half_life_time_days
        )
        adjusted[5] = _rescale_decay(
            original[5], source.params.half_life_hist_days, preview_values.half_life_hist_days
        )
        baseline_bias = float(row.score) - math.fsum(
            weight * feature
            for weight, feature in zip(
                (
                    source.weights.sem,
                    source.weights.kw,
                    source.weights.time,
                    source.weights.proj,
                    source.weights.freq,
                    source.weights.hist,
                ),
                original,
                strict=True,
            )
        )
        baseline_bias -= source.bias_offset(row.memory_id)
        preview_score = (
            math.fsum(
                weight * feature
                for weight, feature in zip(_weight_tuple(preview_values), adjusted, strict=True)
            )
            + baseline_bias
            + preview_runtime.bias_offset(row.memory_id)
        )
        frozen = row.features.get("_memory")
        if not isinstance(frozen, Mapping) or not isinstance(frozen.get("body"), str):
            return InstantSimulation(
                status="not_replayable", injection_id=injection_id, candidates=[]
            )
        candidates.append(
            {
                "row": row,
                "label": frozen.get("label") if isinstance(frozen.get("label"), str) else "",
                "pin": bool(frozen.get("pin")) or row.shown_as == "pinned",
                "token_cost": cl100k_token_count(frozen["body"]),
                "score": preview_score,
            }
        )
    pins = sorted(
        (item for item in candidates if item["pin"]), key=lambda item: item["row"].memory_id.int
    )
    regular = sorted(
        (item for item in candidates if not item["pin"]),
        key=lambda item: (-item["score"], item["row"].memory_id.int),
    )
    ordered = [*pins, *regular]
    preview_selected = {item["row"].memory_id for item in pins}
    pin_cost = sum(item["token_cost"] for item in pins)
    percentage_budget = int(preview_runtime.params.budget_pct * context_tokens)
    remaining = max(0, min(preview_values.budget_tokens, percentage_budget) - pin_cost)
    selected_regular = 0
    for item in regular:
        if (
            selected_regular < preview_values.top_k
            and item["score"] >= preview_values.tau
            and item["token_cost"] <= remaining
        ):
            preview_selected.add(item["row"].memory_id)
            remaining -= item["token_cost"]
            selected_regular += 1
    comparisons: list[ScorerComparisonRow] = []
    for rank, item in enumerate(ordered, start=1):
        row = item["row"]
        incumbent_selected = _event_selected(row)
        selected = row.memory_id in preview_selected
        disposition_name = {
            (True, True): "also_shown",
            (False, True): "would_add",
            (True, False): "would_drop",
            (False, False): "still_out",
        }[(incumbent_selected, selected)]
        comparisons.append(
            ScorerComparisonRow(
                memory_id=row.memory_id,
                label=item["label"],
                incumbent_score=_decimal_string(row.score),
                preview_score=_decimal_string(item["score"]),
                score_delta=_decimal_string(Decimal(str(item["score"])) - Decimal(str(row.score))),
                incumbent_rank=row.rank,
                preview_rank=rank,
                incumbent_selected=incumbent_selected,
                preview_selected=selected,
                disposition=disposition_name,  # type: ignore[arg-type]
            )
        )
    return InstantSimulation(status="ready", injection_id=injection_id, candidates=comparisons)


def _event_selected(row: InjectionEvent) -> bool:
    if row.outcome is None:
        return row.shown_as != "near_miss"
    return row.outcome in {"kept", "added_back", "cited", "auto_entered", "mid_thread_added"}


def _slice_values(values: ScorerValues, parameter_id: str) -> tuple[float | int, ...]:
    if parameter_id == "scorer.top_k":
        return tuple(range(1, 9))
    if parameter_id == "scorer.tau" or parameter_id.startswith("scorer.weight."):
        return tuple(index / 8 for index in range(9))
    current = _flat_values(values)[parameter_id]
    raw = [float(current) * (0.25 + index * (1.75 / 8)) for index in range(9)]
    if parameter_id == "scorer.budget_tokens":
        return tuple(dict.fromkeys(max(1, round(item)) for item in raw))
    return tuple(raw)


def _with_parameter(values: ScorerValues, parameter_id: str, value: float | int) -> ScorerValues:
    payload = values.model_dump(mode="python")
    if parameter_id.startswith("scorer.weight."):
        feature = parameter_id.rsplit(".", 1)[1]
        weights = dict(payload["weights"])
        target = float(value)
        remainder = 1.0 - target
        other_names = [name for name in FEATURE_NAMES if name != feature]
        other_total = math.fsum(weights[name] for name in other_names)
        if other_total == 0:
            for name in other_names:
                weights[name] = remainder / len(other_names)
        else:
            for name in other_names:
                weights[name] = remainder * weights[name] / other_total
        weights[feature] = target
        weights[other_names[-1]] += 1.0 - math.fsum(weights.values())
        payload["weights"] = weights
    else:
        key = parameter_id.removeprefix("scorer.")
        payload[key] = int(value) if key in {"top_k", "budget_tokens"} else float(value)
    return ScorerValues(**payload)


async def _active_config(session: AsyncSession) -> ScorerConfigRow:
    rows = (
        (await session.execute(select(ScorerConfigRow).where(ScorerConfigRow.active.is_(True))))
        .scalars()
        .all()
    )
    if len(rows) != 1:
        raise M2KStateError("invalid_active_scorer")
    return rows[0]


async def _validate_control_replay(
    session: AsyncSession,
    activation: ScorerActivationRow,
    target_version: str,
    body: CreateScorerConfigRequest,
) -> ScorerConfigurationView:
    target = await session.get(ScorerConfigRow, target_version)
    force = activation.changes.get("_force")
    if (
        target is None
        or activation.version != target_version
        or activation.previous_version != body.base_version
        or activation.actor_class != body.actor_class
        or activation.machine_id != body.machine_id
        or activation.reason != "human_control"
        or _values(target) != body.values
        or not isinstance(force, Mapping)
        or force.get("simulation_digest") != body.simulation_digest
    ):
        raise M2KStateError("event_uid_conflict")
    return _config_view(target)


def _decimal_string(value: Any) -> str:
    if isinstance(value, Decimal):
        decimal = value
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M2KStateError("invalid_decimal")
    else:
        if isinstance(value, float) and not math.isfinite(value):
            raise M2KStateError("invalid_decimal")
        decimal = Decimal(str(value))
    rendered = format(decimal, "f")
    if rendered.startswith("-0") and decimal == 0:
        return "0"
    return rendered


__all__ = ["M2KService", "M2KStateError", "SCORER_DESCRIPTORS"]
