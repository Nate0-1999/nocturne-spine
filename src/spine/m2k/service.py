"""Database authority for the A-035 Memory Graph and Injection Console."""

from __future__ import annotations

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
from spine.learner.model import FEATURE_NAMES
from spine.m2k.contracts import (
    AccuracyPoint,
    ActivateScorerConfigRequest,
    CandidateScoreHistory,
    CandidateScorePoint,
    ContributionBreakdown,
    CreateScorerConfigRequest,
    MemoryGraphEdge,
    MemoryGraphNode,
    MemoryGraphQuery,
    MemoryGraphSnapshot,
    ParameterRange,
    RevisionTrailItem,
    ScorerActivationView,
    ScorerConfigurationView,
    ScorerConsoleQuery,
    ScorerConsoleSnapshot,
    ScorerDescriptor,
    ScorerValues,
)

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
        range=ParameterRange(
            minimum=0, maximum=None, step=0.5, exclusive_minimum=True
        ),
        default=14,
    ),
    ScorerDescriptor(
        id="scorer.half_life_hist_days",
        label="Edit-history half-life (days)",
        type="number",
        range=ParameterRange(
            minimum=0, maximum=None, step=0.5, exclusive_minimum=True
        ),
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
    ) -> None:
        self._session_factory = session_factory
        self._graph_edge_sim = graph_edge_sim

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
        similarity = (1 - left.embedding.cosine_distance(right.embedding)).label(
            "similarity"
        )
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
                            event_statement.order_by(
                                InjectionEvent.ts, InjectionEvent.event_uid
                            )
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
                    return await _validate_control_replay(
                        session, replay, target_version, body
                    )
                active = await _active_config(session)
                if active.version != body.base_version:
                    raise M2KStateError("stale_base")
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
                params["_control"] = {
                    "event_uid": body.event_uid,
                    "parent_version": active.version,
                    "actor_class": body.actor_class,
                    "machine_id": body.machine_id,
                    "changed_parameter_ids": sorted(changes),
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
    disagreements = (
        challenger.get("disagreements") if isinstance(challenger, Mapping) else None
    )
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
        features = MemoryFeatures(
            **{name: float(event.features[name]) for name in FEATURE_NAMES}
        )
        contributions = {
            name: Decimal(str(getattr(features, name))) * Decimal(str(config.weights[name]))
            for name in FEATURE_NAMES
        }
        stored_score = Decimal(str(event.score))
        bias = stored_score - sum(contributions.values(), start=Decimal(0))
        grouped[event.memory_id].append(
            CandidateScorePoint(
                event_uid=event.event_uid,
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


def _changes(old: ScorerValues, new: ScorerValues) -> dict[str, dict[str, float | int]]:
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
    result.update(
        {f"scorer.weight.{name}": value for name, value in values.weights.items()}
    )
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


async def _active_config(session: AsyncSession) -> ScorerConfigRow:
    rows = (
        (
            await session.execute(
                select(ScorerConfigRow).where(ScorerConfigRow.active.is_(True))
            )
        )
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
    if (
        target is None
        or activation.version != target_version
        or activation.previous_version != body.base_version
        or activation.actor_class != body.actor_class
        or activation.machine_id != body.machine_id
        or activation.reason != "human_control"
        or _values(target) != body.values
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
