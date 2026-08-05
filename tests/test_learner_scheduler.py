"""The optional schedule invokes the same learner service and shuts down cleanly."""

import asyncio

from spine.learner.scheduler import LearnerScheduler


class _RecordingService:
    def __init__(self) -> None:
        self.called = asyncio.Event()

    async def retrain(self) -> None:
        self.called.set()


async def test_opt_in_scheduler_runs_after_interval_and_stops() -> None:
    """A-031 is defended by verifying that opt in scheduler runs after interval and stops; this
    prevents drift in the opt-in learner scheduling boundary.
    """
    service = _RecordingService()
    scheduler = LearnerScheduler(service, interval_seconds=0.001)  # type: ignore[arg-type]

    scheduler.start()
    await asyncio.wait_for(service.called.wait(), timeout=1.0)
    await scheduler.stop()
