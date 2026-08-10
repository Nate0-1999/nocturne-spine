"""A-051 work notifications wake one process worker without a clock."""

import asyncio

from spine.learner.worker import LearnerWorker


class _RecordingService:
    def __init__(self) -> None:
        self.calls: asyncio.Queue[None] = asyncio.Queue()

    async def retrain_if_due(self) -> None:
        await self.calls.put(None)


async def test_worker_checks_startup_work_and_subsequent_wakes_then_stops() -> None:
    """A-051 is defended by proving crash catch-up and work wakes share one worker task."""

    service = _RecordingService()
    worker = LearnerWorker(service)  # type: ignore[arg-type]

    worker.start()
    await asyncio.wait_for(service.calls.get(), timeout=1.0)
    worker.notify()
    await asyncio.wait_for(service.calls.get(), timeout=1.0)
    await worker.stop()
