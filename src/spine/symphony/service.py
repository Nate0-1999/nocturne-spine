"""Transactional G6 visibility and G11 winner/loser routing."""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.memory import CasUpdate, MemoryUnitChanges, cas_update_memory_unit
from spine.db.models import ApprovalQueueItem, MemoryUnit, SymphonyRunResolution
from spine.ids import mint_ulid
from spine.memory.service import CreateMemoryCommand, MemoryService
from spine.queue.service import QueueService
from spine.symphony.contracts import (
    ResolveRunRequest,
    ResolveRunResponse,
    StageMemoryRequest,
    StageMemoryResponse,
    VisibilityRequest,
    VisibilityResponse,
    record_from_row,
)


class SymphonyConflictError(RuntimeError):
    """A retry or resolution contradicts append-only run history."""


class SymphonyNotFoundError(LookupError):
    """A requested staged run or winner prefix does not exist."""


class SymphonyService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        memory_service: MemoryService,
        queue_service: QueueService,
    ) -> None:
        self._session_factory = session_factory
        self._memory_service = memory_service
        self._queue_service = queue_service

    async def stage(self, request: StageMemoryRequest) -> StageMemoryResponse:
        row = await self._memory_service.stage_symphony(
            CreateMemoryCommand(
                principal_id=request.principal_id,
                label=request.label,
                body=request.body,
                kind=request.kind,
                keywords=request.keywords,
                project_key=request.project_key,
                origin_thread_id=request.origin_thread_id,
                origin_path=request.origin_path,
                origin_location=request.origin_location,
                editor=f"agent:{request.origin_agent}",
                machine_id=request.machine_id,
                revision_reason="symphony/staged",
            ),
            memory_id=request.memory_id,
            run_id=request.run_id,
            origin_agent=request.origin_agent,
        )
        return StageMemoryResponse(memory=record_from_row(row))

    async def visible(self, request: VisibilityRequest) -> VisibilityResponse:
        unit = MemoryUnit.__table__
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(*unit.c)
                        .where(
                            unit.c.principal_id == request.principal_id,
                            or_(
                                unit.c.status == "active",
                                (
                                    (unit.c.status == "staged")
                                    & (unit.c.run_id == request.run_id)
                                    & (unit.c.origin_agent == request.origin_agent)
                                ),
                            ),
                        )
                        .order_by(unit.c.created_at, unit.c.id)
                    )
                )
                .mappings()
                .all()
            )
        return VisibilityResponse(memories=[record_from_row(row) for row in rows])

    async def resolve(self, run_id: str, request: ResolveRunRequest) -> ResolveRunResponse:
        if not _origin_is_in_run(run_id, request.winner_origin_agent):
            raise SymphonyConflictError("winner_origin_agent does not belong to the run")
        context = request.judged_context.model_dump(mode="json")
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:principal_id, 0))"),
                    {"principal_id": request.principal_id},
                )
                existing = await session.get(SymphonyRunResolution, run_id)
                if existing is not None:
                    _require_resolution_replay(existing, request, context)
                else:
                    rows = await self._locked_run_rows(session, run_id)
                    if not rows:
                        raise SymphonyNotFoundError("the run has no staged memories")
                    if any(row["principal_id"] != request.principal_id for row in rows):
                        raise SymphonyConflictError("run_id spans a different principal")
                    winners = [
                        row
                        for row in rows
                        if _is_origin_prefix(request.winner_origin_agent, row["origin_agent"])
                    ]
                    if not winners:
                        raise SymphonyNotFoundError("the winning attempt has no staged memories")
                    winner_ids = {row["id"] for row in winners}
                    await session.execute(
                        insert(SymphonyRunResolution.__table__).values(
                            run_id=run_id,
                            principal_id=request.principal_id,
                            batch_uid=request.batch_uid,
                            winner_origin_agent=request.winner_origin_agent,
                            machine_id=request.machine_id,
                            judged_context=context,
                        )
                    )
                    for row in rows:
                        winner = row["id"] in winner_ids
                        await cas_update_memory_unit(
                            session,
                            CasUpdate(
                                memory_id=row["id"],
                                expected_revision=row["revision"],
                                rev_uid=mint_ulid(),
                                editor="judge",
                                origin_machine_id=request.machine_id,
                                reason=(
                                    "symphony/winner-queued"
                                    if winner
                                    else "symphony/loser-tombstone"
                                ),
                                changes=MemoryUnitChanges(
                                    status="candidate" if winner else "tombstoned"
                                ),
                            ),
                        )
                        if winner:
                            await session.execute(
                                insert(ApprovalQueueItem.__table__).values(
                                    item_uid=mint_ulid(),
                                    candidate_memory_id=row["id"],
                                    principal_id=request.principal_id,
                                    birthplace="symphony",
                                    birthplace_thread_id=None,
                                    batch_uid=request.batch_uid,
                                    source_name=None,
                                    source_sha256=None,
                                    birthplace_run_id=run_id,
                                    birthplace_origin_agent=row["origin_agent"],
                                    judged_context=context,
                                    verdict="new",
                                    neighbor_ids=[],
                                    target_ids=[],
                                    state="pending",
                                )
                            )
        return await self._resolution_response(run_id, request)

    async def _resolution_response(
        self, run_id: str, request: ResolveRunRequest
    ) -> ResolveRunResponse:
        cards = await self._queue_service.list_batch(request.batch_uid, birthplace="symphony")
        unit = MemoryUnit.__table__
        async with self._session_factory() as session:
            losers = (
                (
                    await session.execute(
                        select(*unit.c)
                        .where(
                            unit.c.run_id == run_id,
                            unit.c.principal_id == request.principal_id,
                            unit.c.status == "tombstoned",
                        )
                        .order_by(unit.c.created_at, unit.c.id)
                    )
                )
                .mappings()
                .all()
            )
        return ResolveRunResponse(
            run_id=run_id,
            batch_uid=request.batch_uid,
            winner_origin_agent=request.winner_origin_agent,
            queue_cards=cards,
            losers=[record_from_row(row) for row in losers],
        )

    @staticmethod
    async def _locked_run_rows(session: AsyncSession, run_id: str) -> list[Any]:
        return list(
            (
                await session.execute(
                    select(*MemoryUnit.__table__.c)
                    .where(
                        MemoryUnit.run_id == run_id,
                        MemoryUnit.status == "staged",
                    )
                    .order_by(MemoryUnit.created_at, MemoryUnit.id)
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )


def _origin_is_in_run(run_id: str, origin_agent: str) -> bool:
    return origin_agent == f"{run_id}/root" or origin_agent.startswith(f"{run_id}/root.")


def _is_origin_prefix(prefix: str, candidate: str | None) -> bool:
    return candidate == prefix or bool(candidate and candidate.startswith(f"{prefix}."))


def _require_resolution_replay(
    existing: SymphonyRunResolution,
    request: ResolveRunRequest,
    context: dict[str, Any],
) -> None:
    observed = (
        existing.principal_id,
        existing.batch_uid,
        existing.winner_origin_agent,
        existing.machine_id,
        existing.judged_context,
    )
    expected = (
        request.principal_id,
        request.batch_uid,
        request.winner_origin_agent,
        request.machine_id,
        context,
    )
    if observed != expected:
        raise SymphonyConflictError("the run already has a different resolution")
