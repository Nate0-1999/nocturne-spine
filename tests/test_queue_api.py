"""Live-Postgres proof for M2H queue birth, invisibility, and decisions."""

from uuid import uuid4

import pytest
from conftest import ScriptedEmbeddingProvider, basis_vector, vector_with_cosine
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import ApprovalDecision, ApprovalQueueItem, MemoryEdge, MemoryUnit


def extraction(thread_id, candidate, *, verdict="new", target_ids=None):
    return {
        "principal_id": "owner",
        "thread_id": str(thread_id),
        "machine_id": "mac",
        "editor": "extraction",
        "candidates": [
            {
                "label": candidate,
                "body": candidate,
                "kind": "procedure",
                "keywords": ["queue", "consent"],
                "verdict": verdict,
                "target_ids": [str(value) for value in target_ids or []],
            }
        ],
    }


@pytest.mark.asyncio
async def test_candidate_is_queue_only_and_denial_is_revisioned_signal(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    thread_id = uuid4()
    embedding_provider.set("candidate lesson", basis_vector(0))
    embedding_provider.set("find candidate", basis_vector(0))

    born = await memory_client.post(
        "/v1/extractions", json=extraction(thread_id, "candidate lesson")
    )
    assert born.status_code == 200
    card = born.json()["cards"][0]
    assert card["candidate"]["status"] == "candidate"

    listed = await memory_client.get("/v1/memories")
    searched = await memory_client.post(
        "/v1/search", json={"principal_id": "owner", "query": "find candidate"}
    )
    assert listed.json()["items"] == []
    assert searched.json()["results"] == []

    denied = await memory_client.post(
        f"/v1/approval-queue/{card['item_uid']}/decisions",
        json={
            "decision": "deny",
            "approval_mode": "explicit",
            "actor_class": "human",
            "machine_id": "mac",
        },
    )
    assert denied.status_code == 200
    assert denied.json()["card"]["candidate"]["status"] == "tombstoned"
    async with memory_session_factory() as session:
        row = await session.scalar(
            select(MemoryUnit).where(MemoryUnit.id == card["candidate"]["memory_id"])
        )
        decision_count = await session.scalar(select(func.count()).select_from(ApprovalDecision))
    assert row is not None and row.revision == 2 and row.status == "tombstoned"
    assert decision_count == 1


@pytest.mark.asyncio
async def test_merge_approval_activates_candidate_tombstones_target_and_is_idempotent(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    thread_id = uuid4()
    embedding_provider.set("old lesson", basis_vector(0))
    embedding_provider.set("merged lesson", vector_with_cosine(0.85))
    created = await memory_client.post(
        "/v1/memories",
        json={
            "principal_id": "owner",
            "label": "old",
            "body": "old lesson",
            "kind": "procedure",
            "editor": "human",
            "machine_id": "mac",
        },
    )
    target_id = created.json()["created"]["memory_id"]

    born = await memory_client.post(
        "/v1/extractions",
        json=extraction(thread_id, "merged lesson", verdict="merge", target_ids=[target_id]),
    )
    card = born.json()["cards"][0]
    body = {
        "decision": "approve",
        "approval_mode": "explicit",
        "actor_class": "human",
        "machine_id": "mac",
    }
    first = await memory_client.post(f"/v1/approval-queue/{card['item_uid']}/decisions", json=body)
    second = await memory_client.post(f"/v1/approval-queue/{card['item_uid']}/decisions", json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["decision_uid"] == second.json()["decision_uid"]
    async with memory_session_factory() as session:
        candidate = await session.get(MemoryUnit, card["candidate"]["memory_id"])
        target = await session.get(MemoryUnit, target_id)
        edge_count = await session.scalar(select(func.count()).select_from(MemoryEdge))
        pending = await session.scalar(
            select(func.count())
            .select_from(ApprovalQueueItem)
            .where(ApprovalQueueItem.state == "pending")
        )
    assert candidate is not None and candidate.status == "active"
    assert target is not None and target.status == "tombstoned"
    assert edge_count == 1
    assert pending == 0


@pytest.mark.asyncio
async def test_contradiction_cannot_passively_approve(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
) -> None:
    thread_id = uuid4()
    embedding_provider.set("first claim", basis_vector(0))
    embedding_provider.set("opposite claim", vector_with_cosine(0.85))
    target = await memory_client.post(
        "/v1/memories",
        json={
            "principal_id": "owner",
            "label": "first",
            "body": "first claim",
            "kind": "fact",
            "editor": "human",
            "machine_id": "mac",
        },
    )
    target_id = target.json()["created"]["memory_id"]
    born = await memory_client.post(
        "/v1/extractions",
        json=extraction(thread_id, "opposite claim", verdict="contradict", target_ids=[target_id]),
    )
    item_uid = born.json()["cards"][0]["item_uid"]
    response = await memory_client.post(
        f"/v1/approval-queue/{item_uid}/decisions",
        json={
            "decision": "approve",
            "approval_mode": "passive",
            "actor_class": "passive",
            "machine_id": "mac",
        },
    )
    assert response.status_code == 422
