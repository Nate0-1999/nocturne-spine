"""Live-Postgres acceptance for the A-059 Symphony memory bridge."""

from uuid import UUID, uuid4

import pytest
from conftest import ScriptedEmbeddingProvider, basis_vector
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import ApprovalQueueItem, MemoryRevision, MemoryUnit
from spine.ids import mint_ulid


def _stage(*, run_id: str, origin_agent: str, memory_id: UUID, body: str) -> dict[str, object]:
    return {
        "memory_id": str(memory_id),
        "principal_id": "owner",
        "run_id": run_id,
        "origin_agent": origin_agent,
        "label": body,
        "body": body,
        "kind": "fact",
        "keywords": ["symphony", "lineage"],
        "project_key": "nocturne",
        "origin_path": "spine",
        "machine_id": "worker-host",
    }


@pytest.mark.asyncio
async def test_two_attempt_run_queues_only_winner_and_tombstones_loser_lineage(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-059 and D.2 114 G6/G11 keep siblings private and route only judged winners to consent."""

    run_id = mint_ulid()
    winner = f"{run_id}/root.1"
    loser = f"{run_id}/root.2"
    winner_id = uuid4()
    loser_id = uuid4()
    for body, vector in (
        ("committed corpus", basis_vector(0)),
        ("winner lesson", basis_vector(1)),
        ("loser lesson", basis_vector(2)),
    ):
        embedding_provider.set(body, vector)

    corpus = await memory_client.post(
        "/v1/memories",
        json={
            "principal_id": "owner",
            "label": "corpus",
            "body": "committed corpus",
            "kind": "fact",
            "editor": "human",
            "machine_id": "owner-host",
        },
    )
    staged_winner = await memory_client.post(
        "/v1/symphony/memories",
        json=_stage(
            run_id=run_id,
            origin_agent=winner,
            memory_id=winner_id,
            body="winner lesson",
        ),
    )
    replay_winner = await memory_client.post(
        "/v1/symphony/memories",
        json=_stage(
            run_id=run_id,
            origin_agent=winner,
            memory_id=winner_id,
            body="winner lesson",
        ),
    )
    staged_loser = await memory_client.post(
        "/v1/symphony/memories",
        json=_stage(
            run_id=run_id,
            origin_agent=loser,
            memory_id=loser_id,
            body="loser lesson",
        ),
    )
    assert corpus.status_code == staged_winner.status_code == staged_loser.status_code == 201
    assert replay_winner.status_code == 201
    assert replay_winner.json() == staged_winner.json()

    winner_view = await memory_client.post(
        "/v1/symphony/memories/query",
        json={"principal_id": "owner", "run_id": run_id, "origin_agent": winner},
    )
    loser_view = await memory_client.post(
        "/v1/symphony/memories/query",
        json={"principal_id": "owner", "run_id": run_id, "origin_agent": loser},
    )
    ordinary = await memory_client.get("/v1/memories")
    assert {item["body"] for item in winner_view.json()["memories"]} == {
        "committed corpus",
        "winner lesson",
    }
    assert {item["body"] for item in loser_view.json()["memories"]} == {
        "committed corpus",
        "loser lesson",
    }
    assert [item["body"] for item in ordinary.json()["items"]] == ["committed corpus"]

    batch_uid = uuid4()
    judged = {
        "verdict": "unanimous_pass",
        "summary": "All three seats accept the winner against the fixed charter.",
        "judge_ids": ["motivation", "implementation", "performance"],
        "evidence_refs": ["verification/symphony/two-attempt.json"],
    }
    resolution = {
        "principal_id": "owner",
        "batch_uid": str(batch_uid),
        "winner_origin_agent": winner,
        "machine_id": "conductor-host",
        "judged_context": judged,
    }
    resolved = await memory_client.post(f"/v1/symphony/runs/{run_id}/resolve", json=resolution)
    assert resolved.status_code == 200
    assert [card["candidate"]["body"] for card in resolved.json()["queue_cards"]] == [
        "winner lesson"
    ]
    assert resolved.json()["queue_cards"][0]["birthplace"] == "symphony"
    assert resolved.json()["queue_cards"][0]["judged_context"] == judged
    assert [item["body"] for item in resolved.json()["losers"]] == ["loser lesson"]
    assert resolved.json()["losers"][0]["status"] == "tombstoned"

    pending = await memory_client.get(
        "/v1/approval-queue",
        params={"principal_id": "owner", "birthplace": "symphony"},
    )
    assert pending.status_code == 200
    assert [card["candidate"]["memory_id"] for card in pending.json()["cards"]] == [
        str(winner_id)
    ]

    approved = await memory_client.post(
        f"/v1/approval-queue/batches/{batch_uid}/decisions",
        json={
            "decision": "approve",
            "approval_mode": "explicit",
            "actor_class": "human",
            "machine_id": "owner-host",
        },
    )
    replay_resolution = await memory_client.post(
        f"/v1/symphony/runs/{run_id}/resolve", json=resolution
    )
    changed_resolution = await memory_client.post(
        f"/v1/symphony/runs/{run_id}/resolve",
        json={**resolution, "batch_uid": str(uuid4())},
    )
    assert approved.status_code == replay_resolution.status_code == 200
    assert replay_resolution.json()["queue_cards"][0]["state"] == "approved"
    assert changed_resolution.status_code == 409

    async with memory_session_factory() as session:
        winner_row = await session.get(MemoryUnit, winner_id)
        loser_row = await session.get(MemoryUnit, loser_id)
        staged_count = await session.scalar(
            select(func.count()).select_from(MemoryUnit).where(MemoryUnit.status == "staged")
        )
        queue_count = await session.scalar(
            select(func.count())
            .select_from(ApprovalQueueItem)
            .where(ApprovalQueueItem.birthplace == "symphony")
        )
        loser_reasons = set(
            await session.scalars(
                select(MemoryRevision.reason).where(MemoryRevision.memory_id == loser_id)
            )
        )
    assert winner_row is not None and winner_row.status == "active"
    assert loser_row is not None and loser_row.status == "tombstoned"
    assert loser_row.run_id == run_id and loser_row.origin_agent == loser
    assert staged_count == 0
    assert queue_count == 1
    assert loser_reasons == {"symphony/staged", "symphony/loser-tombstone"}
