"""Minute-cadence refresh loop for ADR-024's non-authoritative views."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

CANONICAL_SPEND_VIEWS = (
    "v_spend_rate",
    "v_thread_cost",
    "v_run_cost",
    "v_memory_cost",
    "v_cache_efficiency",
)


class SpendViewRefresher:
    """Refresh every derived view without ever becoming ledger authority."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        interval_seconds: float = 60.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("spend view refresh interval must be positive")
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def refresh_once(self) -> None:
        """Refresh all five views in a single deterministic order."""

        async with self._session_factory() as session:
            async with session.begin():
                for view in CANONICAL_SPEND_VIEWS:
                    await session.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("spend view refresher is already running")
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="spend-view-refresher")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop.set()
        await task
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.refresh_once()
            except Exception:
                logger.exception("Could not refresh derived spend views")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval_seconds)
            except TimeoutError:
                pass


__all__ = ["CANONICAL_SPEND_VIEWS", "SpendViewRefresher"]
