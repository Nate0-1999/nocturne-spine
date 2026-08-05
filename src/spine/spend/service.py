"""Atomic, replay-safe writes for the append-only spend ledger."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import SpendEvent
from spine.spend.contracts import SpendEventInput, event_values


class SpendEventConflictError(RuntimeError):
    """An event_uid was replayed with a different normalized receipt line."""

    def __init__(self, event_uid: str) -> None:
        self.event_uid = event_uid
        super().__init__(f"spend event {event_uid} conflicts with its append-only receipt")


class SpendService:
    """Own the only write path into ADR-024's authoritative ledger."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, events: Sequence[SpendEventInput]) -> int:
        """Atomically insert or idempotently accept one nonempty receipt batch."""

        if not events:
            raise ValueError("spend receipt batch must not be empty")
        ids = [event.event_uid for event in events]
        if len(set(ids)) != len(ids):
            raise ValueError("spend receipt batch must have unique event_uid values")

        values = [event_values(event) for event in events]
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    postgresql_insert(SpendEvent)
                    .values(values)
                    .on_conflict_do_nothing(index_elements=[SpendEvent.event_uid])
                )
                rows = (
                    (await session.execute(select(SpendEvent).where(SpendEvent.event_uid.in_(ids))))
                    .scalars()
                    .all()
                )
                by_id = {row.event_uid: row for row in rows}
                for event in events:
                    row = by_id.get(event.event_uid)
                    if row is None:  # pragma: no cover - insert/select transaction invariant
                        raise RuntimeError(f"spend event {event.event_uid} was not persisted")
                    if _row_values(row) != event_values(event):
                        raise SpendEventConflictError(event.event_uid)
        return len(events)


def _row_values(row: SpendEvent) -> dict[str, Any]:
    return {
        "event_uid": row.event_uid,
        "ts": row.ts,
        "product_type": row.product_type,
        "quantity_type": row.quantity_type,
        "unit_of_measure": row.unit_of_measure,
        "quantity": row.quantity,
        "cost_usd": row.cost_usd,
        "basis": row.basis,
        "behavior": row.behavior,
        "purpose": row.purpose,
        "principal_id": row.principal_id,
        "machine_id": row.machine_id,
        "origin_agent": row.origin_agent,
        "thread_id": row.thread_id,
        "run_id": row.run_id,
        "prompt_id": row.prompt_id,
        "memory_id": row.memory_id,
        "model": row.model,
        "provider": row.provider,
        "quantization": row.quantization,
        "ref": row.ref,
        "meta": row.meta,
    }


__all__ = ["SpendEventConflictError", "SpendService"]
