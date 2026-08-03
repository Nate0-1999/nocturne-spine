"""Opt-in periodic trigger for the same M2F retraining operation."""

from __future__ import annotations

import asyncio
import logging

from spine.learner.service import LearnerService

logger = logging.getLogger(__name__)


class LearnerScheduler:
    def __init__(self, service: LearnerService, *, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("learner schedule interval must be positive")
        self._service = service
        self._interval_seconds = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("learner scheduler is already running")
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="chrysopoeia-learner")

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
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval_seconds)
            except TimeoutError:
                try:
                    await self._service.retrain()
                except Exception:
                    logger.exception("Scheduled Chrysopoeia retrain failed")


__all__ = ["LearnerScheduler"]
