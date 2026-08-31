"""Bounded background wake loop for the durable admitted-write trigger."""

from __future__ import annotations

import asyncio
import logging

from spine.curation.service import CuratorService

logger = logging.getLogger(__name__)


class CuratorWorker:
    """Poll durable work truth; elapsed time never makes a pass due."""

    def __init__(self, service: CuratorService, *, poll_seconds: float = 5.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("curator poll interval must be positive")
        self._service = service
        self._poll_seconds = poll_seconds
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping.clear()
            self._task = asyncio.create_task(self._run(), name="spine-curator-worker")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stopping.set()
        await task
        self._task = None

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._service.run_due()
            except Exception:
                logger.exception("Curator worker pass failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._poll_seconds)
            except TimeoutError:
                continue


__all__ = ["CuratorWorker"]
