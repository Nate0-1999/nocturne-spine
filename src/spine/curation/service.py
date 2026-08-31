"""M3CU orchestration: trigger -> report -> verdict -> deterministic queue tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.curation.contracts import (
    CuratorActivity,
    CuratorRunReceipt,
    CuratorVerdictDraft,
    HealthFinding,
    PalaceHealthReport,
)
from spine.curation.diagnostics import HealthReportBuilder
from spine.curation.provider import CuratorProviderError, CuratorVerdictProvider
from spine.db.models import (
    ApprovalQueueItem,
    CuratorAction,
    CuratorFinding,
    CuratorRun,
    CuratorTriggerState,
    CuratorVerdict,
)
from spine.ids import mint_ulid
from spine.queue.service import QueueService

Trigger = Literal["writes", "manual", "injection_pressure", "cron"]


@dataclass(frozen=True, slots=True)
class _JudgedFinding:
    finding_uid: str
    verdict_uid: str
    finding: HealthFinding
    draft: CuratorVerdictDraft
    suppressed: bool


class CuratorService:
    """Own one bounded, palace-anchored curator pass at a time per principal."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        report_builder: HealthReportBuilder,
        verdict_provider: CuratorVerdictProvider,
        queue_service: QueueService,
        *,
        trigger_every: int = 25,
    ) -> None:
        if trigger_every <= 0:
            raise ValueError("curator_write_trigger must be positive")
        self._session_factory = session_factory
        self._report_builder = report_builder
        self._provider = verdict_provider
        self._queue_service = queue_service
        self._trigger_every = trigger_every

    async def run_due(self) -> list[CuratorRunReceipt]:
        """Run each principal whose durable admitted-write cursor crossed the threshold."""

        state = CuratorTriggerState.__table__
        async with self._session_factory() as session:
            principals = (
                (
                    await session.execute(
                        select(state.c.principal_id)
                        .where(
                            state.c.admitted_writes - state.c.last_run_writes
                            >= self._trigger_every
                        )
                        .order_by(state.c.principal_id.asc())
                    )
                )
                .scalars()
                .all()
            )
        receipts: list[CuratorRunReceipt] = []
        for principal_id in principals:
            receipt = await self.run(principal_id, machine_id="spine:curator", trigger="writes")
            if receipt is not None:
                receipts.append(receipt)
        return receipts

    async def run(
        self,
        principal_id: str,
        *,
        machine_id: str,
        trigger: Trigger = "manual",
    ) -> CuratorRunReceipt | None:
        """Run one pass, refusing concurrent duplicate work with a database advisory lock."""

        async with self._session_factory() as lock_session:
            acquired = bool(
                await lock_session.scalar(
                    text(
                        "SELECT pg_try_advisory_lock("
                        "hashtextextended('curator:' || :principal_id, 0))"
                    ),
                    {"principal_id": principal_id},
                )
            )
            if not acquired:
                return None
            try:
                return await self._run_locked(
                    principal_id,
                    machine_id=machine_id,
                    trigger=trigger,
                )
            finally:
                await lock_session.scalar(
                    text(
                        "SELECT pg_advisory_unlock("
                        "hashtextextended('curator:' || :principal_id, 0))"
                    ),
                    {"principal_id": principal_id},
                )

    async def activity(self, principal_id: str) -> CuratorActivity:
        state = CuratorTriggerState.__table__
        run = CuratorRun.__table__
        queue = ApprovalQueueItem.__table__
        async with self._session_factory() as session:
            state_row = (
                (
                    await session.execute(
                        select(*state.c).where(state.c.principal_id == principal_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
            run_row = (
                (
                    await session.execute(
                        select(*run.c)
                        .where(run.c.principal_id == principal_id)
                        .order_by(run.c.completed_at.desc(), run.c.run_uid.desc())
                        .limit(1)
                    )
                )
                .mappings()
                .one_or_none()
            )
            pending = await session.scalar(
                select(func.count())
                .select_from(queue)
                .where(
                    queue.c.principal_id == principal_id,
                    queue.c.birthplace == "curator",
                    queue.c.state == "pending",
                )
            )
        admitted = 0 if state_row is None else int(state_row["admitted_writes"])
        cursor = 0 if state_row is None else int(state_row["last_run_writes"])
        outstanding = max(0, admitted - cursor)
        return CuratorActivity(
            principal_id=principal_id,
            admitted_writes=admitted,
            last_run_writes=cursor,
            trigger_every=self._trigger_every,
            writes_until_run=max(0, self._trigger_every - outstanding),
            latest_run=None if run_row is None else _receipt(run_row),
            pending_cards=int(pending or 0),
        )

    async def _run_locked(
        self,
        principal_id: str,
        *,
        machine_id: str,
        trigger: Trigger,
    ) -> CuratorRunReceipt:
        run_uid = mint_ulid()
        report = await self._report_builder.build(principal_id)
        admitted = await self._admitted_writes(principal_id)
        judged: list[_JudgedFinding] = []
        try:
            for finding in report.findings:
                finding_uid = mint_ulid()
                verdict_uid = mint_ulid()
                draft = await self._provider.verdict(
                    finding,
                    report,
                    run_uid=run_uid,
                    machine_id=machine_id,
                )
                _require_allowed(finding, draft)
                suppressed = await self._was_seen_unchanged(finding, draft.action)
                judged.append(
                    _JudgedFinding(
                        finding_uid=finding_uid,
                        verdict_uid=verdict_uid,
                        finding=finding,
                        draft=draft,
                        suppressed=suppressed,
                    )
                )
        except Exception as exc:
            error = _bounded_error(exc)
            await self._persist_failed(
                run_uid,
                principal_id=principal_id,
                trigger=trigger,
                report=report,
                admitted=admitted,
                error=error,
            )
            return await self._run_receipt(run_uid)

        actions: list[tuple[_JudgedFinding, str, str | None, dict[str, Any]]] = []
        queued = 0
        for item in judged:
            proposal = item.draft.model_dump(mode="json", exclude_none=True)
            proposal["finding_fingerprint"] = item.finding.fingerprint
            if item.suppressed:
                actions.append(
                    (item, "noop", None, {"reason": "unchanged rejected proposal"})
                )
                continue
            if item.draft.action == "keep":
                actions.append((item, "noop", None, {"reason": "surgeon verdict kept corpus"}))
                continue
            try:
                card = await self._queue_service.enqueue_curator(
                    run_uid=run_uid,
                    finding_uid=item.finding_uid,
                    principal_id=principal_id,
                    machine_id=machine_id,
                    action=item.draft.action,
                    memory_ids=item.finding.memory_ids,
                    proposal=proposal,
                )
            except Exception as exc:
                actions.append(
                    (item, "refused", None, {"reason": _bounded_error(exc)})
                )
                continue
            if card is None:
                actions.append(
                    (item, "refused", None, {"reason": "proposal collided with live corpus"})
                )
                continue
            queued += 1
            actions.append(
                (
                    item,
                    "queued",
                    card.item_uid,
                    {"verdict": item.draft.action, "finding": item.finding.fingerprint},
                )
            )

        await self._persist_completed(
            run_uid,
            principal_id=principal_id,
            trigger=trigger,
            report=report,
            admitted=admitted,
            judged=judged,
            actions=actions,
            queued=queued,
        )
        await self._advance_cursor(principal_id, admitted)
        return await self._run_receipt(run_uid)

    async def _admitted_writes(self, principal_id: str) -> int:
        async with self._session_factory() as session:
            value = await session.scalar(
                select(CuratorTriggerState.admitted_writes).where(
                    CuratorTriggerState.principal_id == principal_id
                )
            )
        return int(value or 0)

    async def _was_seen_unchanged(self, finding: HealthFinding, action: str) -> bool:
        async with self._session_factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(CuratorFinding)
                .join(CuratorVerdict, CuratorVerdict.finding_uid == CuratorFinding.finding_uid)
                .join(
                    ApprovalQueueItem,
                    ApprovalQueueItem.curator_finding_uid == CuratorFinding.finding_uid,
                )
                .where(
                    CuratorFinding.fingerprint == finding.fingerprint,
                    CuratorVerdict.action == action,
                    ApprovalQueueItem.state.in_(("pending", "rejected")),
                )
            )
        return bool(count)

    async def _persist_failed(
        self,
        run_uid: str,
        *,
        principal_id: str,
        trigger: Trigger,
        report: PalaceHealthReport,
        admitted: int,
        error: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    insert(CuratorRun).values(
                        run_uid=run_uid,
                        principal_id=principal_id,
                        trigger=trigger,
                        report_version=report.version,
                        report=report.model_dump(mode="json"),
                        admitted_writes_snapshot=admitted,
                        verdict_count=0,
                        queued_count=0,
                        executed_count=0,
                        status="failed",
                        error=error,
                    )
                )

    async def _persist_completed(
        self,
        run_uid: str,
        *,
        principal_id: str,
        trigger: Trigger,
        report: PalaceHealthReport,
        admitted: int,
        judged: list[_JudgedFinding],
        actions: list[tuple[_JudgedFinding, str, str | None, dict[str, Any]]],
        queued: int,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    insert(CuratorRun).values(
                        run_uid=run_uid,
                        principal_id=principal_id,
                        trigger=trigger,
                        report_version=report.version,
                        report=report.model_dump(mode="json"),
                        admitted_writes_snapshot=admitted,
                        verdict_count=len(judged),
                        queued_count=queued,
                        executed_count=0,
                        status="completed",
                        error=None,
                    )
                )
                for item in judged:
                    await session.execute(
                        insert(CuratorFinding).values(
                            finding_uid=item.finding_uid,
                            run_uid=run_uid,
                            ordinal=item.finding.ordinal,
                            kind=item.finding.kind,
                            memory_ids=[str(value) for value in item.finding.memory_ids],
                            evidence=item.finding.evidence,
                            fingerprint=item.finding.fingerprint,
                        )
                    )
                    await session.execute(
                        insert(CuratorVerdict).values(
                            verdict_uid=item.verdict_uid,
                            finding_uid=item.finding_uid,
                            action=item.draft.action,
                            rationale=item.draft.rationale,
                            proposal=item.draft.model_dump(mode="json", exclude_none=True),
                        )
                    )
                for item, outcome, queue_item_uid, detail in actions:
                    await session.execute(
                        insert(CuratorAction).values(
                            action_uid=mint_ulid(),
                            verdict_uid=item.verdict_uid,
                            finding_uid=item.finding_uid,
                            queue_item_uid=queue_item_uid,
                            outcome=outcome,
                            detail=detail,
                        )
                    )

    async def _advance_cursor(self, principal_id: str, admitted: int) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    postgresql_insert(CuratorTriggerState)
                    .values(
                        principal_id=principal_id,
                        admitted_writes=admitted,
                        last_run_writes=admitted,
                    )
                    .on_conflict_do_update(
                        index_elements=[CuratorTriggerState.principal_id],
                        set_={"last_run_writes": admitted, "updated_at": func.now()},
                    )
                )

    async def _run_receipt(self, run_uid: str) -> CuratorRunReceipt:
        async with self._session_factory() as session:
            row = (
                (
                    await session.execute(
                        select(*CuratorRun.__table__.c).where(CuratorRun.run_uid == run_uid)
                    )
                )
                .mappings()
                .one()
            )
        return _receipt(row)


def _receipt(row: Any) -> CuratorRunReceipt:
    return CuratorRunReceipt(
        run_uid=row["run_uid"],
        principal_id=row["principal_id"],
        trigger=row["trigger"],
        status=row["status"],
        admitted_writes_snapshot=row["admitted_writes_snapshot"],
        verdict_count=row["verdict_count"],
        queued_count=row["queued_count"],
        executed_count=row["executed_count"],
        report=PalaceHealthReport.model_validate(row["report"]),
        error=row["error"],
        completed_at=row["completed_at"],
    )


def _require_allowed(finding: HealthFinding, draft: CuratorVerdictDraft) -> None:
    allowed = {
        "duplicate": {"keep", "merge"},
        "contradiction": {"keep", "contradict", "supersede"},
        "stale": {"keep", "supersede", "retire"},
        "slop": {"keep", "retire", "split"},
        "keyword": {"keep", "keyword_repair"},
    }[finding.kind]
    if draft.action not in allowed:
        raise CuratorProviderError(
            f"curator returned {draft.action!r} for {finding.kind!r}; allowed: {sorted(allowed)}"
        )


def _bounded_error(exc: Exception) -> str:
    message = " ".join(str(exc).split()) or type(exc).__name__
    return message[:500]


__all__ = ["CuratorService"]
