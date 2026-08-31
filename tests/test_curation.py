"""M3CU live-Postgres proof for deterministic reports and bounded curator tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from conftest import ScriptedEmbeddingProvider, basis_vector, vector_with_cosine
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.curation.contracts import CuratorVerdictDraft, HealthFinding, PalaceHealthReport
from spine.curation.diagnostics import HealthReportBuilder
from spine.curation.service import CuratorService
from spine.db.models import (
    ApprovalQueueItem,
    CuratorAction,
    CuratorFinding,
    CuratorRun,
    MemoryEdge,
    MemoryRevision,
    MemoryUnit,
)
from spine.queue.contracts import QueueDecisionRequest


class FixtureCuratorProvider:
    """Deterministic judgment fake; production uses the OpenRouter implementation."""

    async def verdict(
        self,
        finding: HealthFinding,
        report: PalaceHealthReport,
        *,
        run_uid: str,
        machine_id: str,
    ) -> CuratorVerdictDraft:
        del report, run_uid, machine_id
        if finding.kind == "duplicate":
            return CuratorVerdictDraft(
                action="merge",
                rationale="These two units state the same durable fact.",
                label="Merged duplicate",
                body="One canonical statement preserves the duplicated fact.",
                keywords=["canonical", "duplicate"],
            )
        if finding.kind == "slop":
            return CuratorVerdictDraft(
                action="retire",
                rationale="Repeated removals and no citations make this unit harmful.",
            )
        return CuratorVerdictDraft(action="keep", rationale="No bounded change is justified.")


def _memory(label: str, body: str, *, force: bool = False) -> dict[str, Any]:
    return {
        "principal_id": "fixture-owner",
        "label": label,
        "body": body,
        "kind": "fact",
        "keywords": ["fixture", label.lower()],
        "editor": "human",
        "machine_id": "fixture-mac",
        "force": force,
    }


async def _seed_mess(
    client: AsyncClient,
    embeddings: ScriptedEmbeddingProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID, UUID]:
    bodies = ("The archive closes at nine.", "Archive closing time is nine.", "Maybe useful.")
    embeddings.set(bodies[0], basis_vector(0))
    embeddings.set(bodies[1], vector_with_cosine(0.90))
    embeddings.set(bodies[2], basis_vector(2))
    embeddings.set("One canonical statement preserves the duplicated fact.", basis_vector(3))
    first = await client.post("/v1/memories", json=_memory("First", bodies[0]))
    second = await client.post("/v1/memories", json=_memory("Second", bodies[1], force=True))
    slop = await client.post("/v1/memories", json=_memory("Slop", bodies[2]))
    assert (first.status_code, second.status_code, slop.status_code) == (201, 201, 201)
    ids = tuple(
        UUID(response.json()["created"]["memory_id"])
        for response in (first, second, slop)
    )
    async with session_factory() as session, session.begin():
        await session.execute(
            update(MemoryUnit)
            .where(MemoryUnit.id == ids[2])
            .values(stats={"citations": 0, "removals": 3, "reinforcements": 0, "last_cited": None})
        )
    return ids  # type: ignore[return-value]


def _install_fixture_curator(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> CuratorService:
    service = CuratorService(
        session_factory,
        HealthReportBuilder(session_factory, duplicate_floor=0.89),
        FixtureCuratorProvider(),
        app.state.queue_service,
        trigger_every=3,
    )
    app.state.curator_service = service
    return service


@pytest.mark.asyncio
async def test_health_report_is_byte_stable_for_one_snapshot(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_mess(memory_client, embedding_provider, memory_session_factory)
    builder = HealthReportBuilder(memory_session_factory, duplicate_floor=0.89)
    observed_at = datetime(2026, 8, 31, 12, tzinfo=UTC)

    first = await builder.build("fixture-owner", as_of=observed_at)
    second = await builder.build("fixture-owner", as_of=observed_at)

    assert first.model_dump_json() == second.model_dump_json()
    assert [finding.kind for finding in first.findings] == ["duplicate", "slop"]
    assert first.stats_delta == {
        "revisions": 3,
        "reinforcements": 0,
        "merges": 0,
        "retirements": 0,
    }


@pytest.mark.asyncio
async def test_messy_palace_runs_queues_and_tidies_only_after_explicit_consent(
    memory_client: AsyncClient,
    memory_app: FastAPI,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    source_ids = await _seed_mess(memory_client, embedding_provider, memory_session_factory)
    service = _install_fixture_curator(memory_app, memory_session_factory)

    receipt = await service.run("fixture-owner", machine_id="fixture-mac", trigger="writes")
    assert receipt is not None
    run_counts = (
        receipt.status,
        receipt.verdict_count,
        receipt.queued_count,
        receipt.executed_count,
    )
    assert run_counts == (
        "completed",
        2,
        2,
        0,
    )
    before_consent = await service.activity("fixture-owner")
    assert before_consent.pending_cards == 2
    async with memory_session_factory() as session:
        active_before = await session.scalar(
            select(func.count()).select_from(MemoryUnit).where(MemoryUnit.status == "active")
        )
        cards = (
            await session.scalars(
                select(ApprovalQueueItem)
                .where(ApprovalQueueItem.birthplace == "curator")
                .order_by(ApprovalQueueItem.verdict)
            )
        ).all()
    assert active_before == 3

    for card in cards:
        await memory_app.state.queue_service.decide(
            card.item_uid,
            QueueDecisionRequest(
                decision="approve",
                approval_mode="explicit",
                actor_class="human",
                machine_id="fixture-mac",
            ),
        )

    async with memory_session_factory() as session:
        active_after = await session.scalar(
            select(func.count()).select_from(MemoryUnit).where(MemoryUnit.status == "active")
        )
        source_statuses = dict(
            (
                await session.execute(
                    select(MemoryUnit.id, MemoryUnit.status).where(MemoryUnit.id.in_(source_ids))
                )
            ).all()
        )
        reasons = set(
            await session.scalars(
                select(MemoryRevision.reason).where(MemoryRevision.editor == "maintenance")
            )
        )
        edges = await session.scalar(
            select(func.count())
            .select_from(MemoryEdge)
            .where(MemoryEdge.edge_type == "merged_from")
        )
        actions = await session.scalar(select(func.count()).select_from(CuratorAction))
    assert active_after == 1
    assert set(source_statuses.values()) == {"tombstoned"}
    assert edges == 2
    assert actions == 2
    assert all(reason.startswith("curation/") for reason in reasons)
    assert any(reason.endswith("/merge") for reason in reasons)
    assert any(reason.endswith("/retire") for reason in reasons)


@pytest.mark.asyncio
async def test_rejected_unchanged_verdict_is_not_queued_again(
    memory_client: AsyncClient,
    memory_app: FastAPI,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_mess(memory_client, embedding_provider, memory_session_factory)
    service = _install_fixture_curator(memory_app, memory_session_factory)
    first = await service.run("fixture-owner", machine_id="fixture-mac")
    assert first is not None
    async with memory_session_factory() as session:
        merge_card = await session.scalar(
            select(ApprovalQueueItem).where(ApprovalQueueItem.verdict == "merge")
        )
    assert merge_card is not None
    await memory_app.state.queue_service.decide(
        merge_card.item_uid,
        QueueDecisionRequest(
            decision="deny",
            approval_mode="explicit",
            actor_class="human",
            machine_id="fixture-mac",
        ),
    )

    second = await service.run("fixture-owner", machine_id="fixture-mac")
    assert second is not None
    assert second.queued_count == 0
    async with memory_session_factory() as session:
        merge_cards = await session.scalar(
            select(func.count())
            .select_from(ApprovalQueueItem)
            .where(ApprovalQueueItem.verdict == "merge")
        )
    assert merge_cards == 1


@pytest.mark.asyncio
async def test_split_tool_preserves_lineage_and_public_maintenance_bypass_is_refused(
    memory_client: AsyncClient,
    memory_app: FastAPI,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    source_body = "Alpha guidance. Beta guidance."
    embedding_provider.set(source_body, basis_vector(0))
    embedding_provider.set("Alpha guidance.", basis_vector(1))
    embedding_provider.set("Beta guidance.", basis_vector(2))
    source_response = await memory_client.post(
        "/v1/memories", json=_memory("Mixed", source_body)
    )
    source_id = UUID(source_response.json()["created"]["memory_id"])
    card = await memory_app.state.queue_service.enqueue_curator(
        run_uid="01K3CURATORRUN000000000000",
        finding_uid="01K3CURATORFIND00000000000",
        principal_id="fixture-owner",
        machine_id="fixture-mac",
        action="split",
        memory_ids=[source_id],
        proposal={
            "action": "split",
            "rationale": "The source contains two semantic units.",
            "finding_fingerprint": "0" * 64,
            "children": [
                {
                    "label": "Alpha",
                    "body": "Alpha guidance.",
                    "kind": "fact",
                    "keywords": ["alpha", "guidance"],
                },
                {
                    "label": "Beta",
                    "body": "Beta guidance.",
                    "kind": "fact",
                    "keywords": ["beta", "guidance"],
                },
            ],
        },
    )
    assert card is not None
    await memory_app.state.queue_service.decide(
        card.item_uid,
        QueueDecisionRequest(
            decision="approve",
            approval_mode="explicit",
            actor_class="human",
            machine_id="fixture-mac",
        ),
    )
    bypass = await memory_client.patch(
        f"/v1/memories/{source_id}",
        json={
            "expected_revision": 2,
            "status": "active",
            "editor": "maintenance",
            "reason": "free hand",
            "machine_id": "rogue-curator",
        },
    )
    assert bypass.status_code == 422
    assert "bounded curator queue tools" in bypass.json()["detail"]

    async with memory_session_factory() as session:
        source = await session.get(MemoryUnit, source_id)
        children = (
            await session.scalars(
                select(MemoryUnit).where(
                    MemoryUnit.principal_id == "fixture-owner",
                    MemoryUnit.id != source_id,
                )
            )
        ).all()
        revisions = (
            await session.scalars(
                select(MemoryRevision).where(
                    MemoryRevision.memory_id.in_([child.id for child in children])
                )
            )
        ).all()
        source_tombstone = await session.scalar(
            select(MemoryRevision).where(
                MemoryRevision.memory_id == source_id,
                MemoryRevision.revision == 2,
            )
        )
        sibling_edges = await session.scalar(
            select(func.count()).select_from(MemoryEdge).where(MemoryEdge.edge_type == "relates_to")
        )
    assert source is not None and source.status == "tombstoned" and source.revision == 2
    assert len(children) == 2 and {child.status for child in children} == {"active"}
    assert source_tombstone is not None
    assert {revision.parent_uid for revision in revisions} == {source_tombstone.rev_uid}
    assert sibling_edges == 2


@pytest.mark.asyncio
async def test_curator_history_tables_are_append_only(
    memory_client: AsyncClient,
    memory_app: FastAPI,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_mess(memory_client, embedding_provider, memory_session_factory)
    service = _install_fixture_curator(memory_app, memory_session_factory)
    receipt = await service.run("fixture-owner", machine_id="fixture-mac")
    assert receipt is not None
    async with memory_session_factory() as session:
        with pytest.raises(DBAPIError, match="curator history is append-only"):
            async with session.begin():
                await session.execute(
                    update(CuratorRun)
                    .where(CuratorRun.run_uid == receipt.run_uid)
                    .values(status="failed", error="tampered")
                )
    async with memory_session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(CuratorFinding))
    assert count == 2
