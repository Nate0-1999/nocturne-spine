"""Atomic append and exact replay service for transcript resurrection."""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import TranscriptRecord
from spine.transcripts.contracts import (
    AppendTranscriptsRequest,
    TranscriptAppendResult,
    TranscriptList,
    TranscriptRecordView,
    TranscriptStatus,
)


class TranscriptConflict(RuntimeError):
    """The proposed append disagrees with the immutable Palace prefix."""


class TranscriptService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, body: AppendTranscriptsRequest) -> TranscriptAppendResult:
        accepted = 0
        replayed = 0
        async with self._session_factory() as session, session.begin():
            lock_key = int.from_bytes(
                hashlib.sha256(body.principal_id.encode()).digest()[:8], "big", signed=True
            )
            await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
            for record in body.records:
                existing = await session.get(
                    TranscriptRecord,
                    (body.principal_id, record.thread_id, record.sequence),
                )
                if existing is not None:
                    if (
                        existing.journal_line != record.journal_line
                        or existing.sha256 != record.sha256
                    ):
                        raise TranscriptConflict("changed_replay")
                    replayed += 1
                    continue
                latest = await session.scalar(
                    select(func.max(TranscriptRecord.sequence)).where(
                        TranscriptRecord.principal_id == body.principal_id,
                        TranscriptRecord.thread_id == record.thread_id,
                    )
                )
                if record.sequence != (latest or 0) + 1:
                    raise TranscriptConflict("non_contiguous_sequence")
                session.add(
                    TranscriptRecord(
                        principal_id=body.principal_id,
                        thread_id=record.thread_id,
                        sequence=record.sequence,
                        journal_line=record.journal_line,
                        sha256=record.sha256,
                    )
                )
                await session.flush()
                accepted += 1
            status = await self._status(session, body.principal_id)
        return TranscriptAppendResult(accepted=accepted, replayed=replayed, status=status)

    async def list(self, principal_id: str) -> TranscriptList:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(TranscriptRecord)
                        .where(TranscriptRecord.principal_id == principal_id)
                        .order_by(TranscriptRecord.thread_id, TranscriptRecord.sequence)
                    )
                )
                .scalars()
                .all()
            )
        return TranscriptList(
            principal_id=principal_id,
            records=[self._view(row) for row in rows],
        )

    async def status(self, principal_id: str) -> TranscriptStatus:
        async with self._session_factory() as session:
            return await self._status(session, principal_id)

    async def _status(self, session: AsyncSession, principal_id: str) -> TranscriptStatus:
        row = (
            await session.execute(
                select(
                    func.count(TranscriptRecord.sequence),
                    func.count(func.distinct(TranscriptRecord.thread_id)),
                    func.max(TranscriptRecord.received_at),
                ).where(TranscriptRecord.principal_id == principal_id)
            )
        ).one()
        return TranscriptStatus(
            principal_id=principal_id,
            record_count=row[0],
            thread_count=row[1],
            latest_received_at=row[2],
        )

    @staticmethod
    def _view(row: TranscriptRecord) -> TranscriptRecordView:
        return TranscriptRecordView(
            thread_id=row.thread_id,
            sequence=row.sequence,
            journal_line=row.journal_line,
            sha256=row.sha256,
            received_at=row.received_at,
        )
