"""M2M proof for cumulative broker reconciliation and Vitals drift. [A-037]"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.spend.reconciliation import (
    BrokerUnavailable,
    OpenRouterUsageClient,
    ReconciliationScheduler,
    ReconciliationService,
)
from spine.vitals.service import VitalsService


class _Gateway:
    def __init__(self, *values: Decimal | Exception) -> None:
        self.values = list(values)

    async def cumulative_usage_usd(self) -> Decimal:
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


async def _receipt(
    sessions: async_sessionmaker[AsyncSession],
    uid: str,
    cost: str | None,
) -> None:
    async with sessions.begin() as session:
        await session.execute(
            text(
                "INSERT INTO spend_event "
                "(event_uid, ts, product_type, quantity_type, unit_of_measure, quantity, "
                "cost_usd, basis, behavior, purpose, ref) VALUES "
                "(:uid, now(), 'llm.request', 'output', 'tokens', 1, :cost, "
                "'measured', 'variable', 'building', :uid)"
            ),
            {"uid": uid, "cost": cost},
        )


async def test_baseline_balanced_drift_and_vitals_projection(
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _receipt(memory_session_factory, "01K1M2M0000000000000000001", "1.000000")
    gateway = _Gateway(Decimal("10"), Decimal("10.25"), Decimal("10.30"))
    service = ReconciliationService(
        memory_session_factory,
        gateway,
        tolerance_usd=Decimal("0.000001"),
    )

    baseline = await service.reconcile_once()
    await _receipt(memory_session_factory, "01K1M2M0000000000000000002", "0.250000")
    balanced = await service.reconcile_once()
    await _receipt(memory_session_factory, "01K1M2M0000000000000000003", "0.100000")
    drift = await service.reconcile_once()

    assert baseline.status == "baseline"
    assert balanced.status == "balanced"
    assert drift.status == "drift"
    assert drift.broker_since_baseline_usd == Decimal("0.300000000000")
    assert drift.ledger_since_baseline_usd == Decimal("0.350000000000")
    assert drift.drift_usd == Decimal("0.050000000000")

    snapshot = await VitalsService(
        memory_session_factory,
        reconciliation_configured=True,
    ).snapshot()
    assert snapshot.reconciliation.status == "drift"
    assert snapshot.reconciliation.drift_usd == "0.050000000000"
    assert snapshot.reconciliation.source == "openrouter:/api/v1/key"


async def test_unavailable_is_safe_and_reconciliation_rows_are_append_only(
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = ReconciliationService(
        memory_session_factory,
        _Gateway(BrokerUnavailable("secret-bearing upstream error")),
        tolerance_usd=Decimal("0.000001"),
    )
    row = await service.reconcile_once()

    assert row.status == "unavailable"
    assert row.error_code == "broker_unavailable"
    assert row.broker_usage_usd is None
    async with memory_session_factory() as session:
        with pytest.raises(DBAPIError, match="spend_reconciliation is append-only"):
            async with session.begin():
                await session.execute(
                    text("DELETE FROM spend_reconciliation WHERE event_uid = :uid"),
                    {"uid": row.event_uid},
                )


async def test_openrouter_client_reads_only_current_key_usage() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/key"
        assert request.headers["authorization"] == "Bearer existing-key"
        return httpx.Response(200, json={"data": {"usage": 12.345678901234}})

    client = OpenRouterUsageClient(
        api_key="existing-key",
        base_url="https://openrouter.ai/api/v1",
    )
    await client._client.aclose()  # noqa: SLF001 - replace transport at this seam
    client._client = httpx.AsyncClient(  # noqa: SLF001
        base_url="https://openrouter.ai/api/v1",
        headers={"Authorization": "Bearer existing-key"},
        transport=httpx.MockTransport(handler),
    )
    try:
        assert await client.cumulative_usage_usd() == Decimal("12.345678901234")
    finally:
        await client.aclose()


async def test_scheduler_runs_immediately_and_stops_cleanly() -> None:
    class Service:
        def __init__(self) -> None:
            self.called = asyncio.Event()
            self.calls = 0

        async def reconcile_once(self) -> None:
            self.calls += 1
            self.called.set()

    service = Service()
    scheduler = ReconciliationScheduler(service, interval_seconds=60)  # type: ignore[arg-type]
    scheduler.start()
    await asyncio.wait_for(service.called.wait(), timeout=1)
    await scheduler.stop()
    assert service.calls == 1
