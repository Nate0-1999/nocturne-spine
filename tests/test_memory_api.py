"""S2 live-Postgres contract tests for memory create, patch, and list."""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import tiktoken
from conftest import ScriptedEmbeddingProvider, basis_vector, vector_with_cosine
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import MemoryRevision, MemoryUnit

ULID_PATTERN = re.compile(r"[0-7][0-9A-HJKMNP-TV-Z]{25}\Z")


def _create_body(
    *,
    label: str,
    body: str,
    principal_id: str = "owner",
    **overrides: Any,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "principal_id": principal_id,
        "label": label,
        "body": body,
        "kind": "fact",
        "editor": "test-editor",
        "machine_id": "test-machine",
    }
    request.update(overrides)
    return request


def _patch_body(expected_revision: int, **changes: Any) -> dict[str, Any]:
    request: dict[str, Any] = {
        "expected_revision": expected_revision,
        "editor": "patch-editor",
        "reason": "test change",
        "machine_id": "patch-machine",
    }
    request.update(changes)
    return request


def _assert_json(response: Response, status: int) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].split(";", 1)[0] == "application/json"
    return response.json()


def _assert_problem(response: Response, status: int, endpoint: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].split(";", 1)[0] == "application/problem+json"
    problem = response.json()
    assert problem["type"] == "about:blank"
    assert problem["status"] == status
    assert problem["title"]
    assert problem["detail"]
    assert problem["endpoint"] == endpoint
    return problem


async def test_create_writes_root_attribution_and_checks_label_before_embedding(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    embedding_provider.set("Original body", basis_vector(0))

    created_response = await memory_client.post(
        "/v1/memories",
        json=_create_body(
            label="Original label",
            body="Original body",
            kind="preference",
            keywords=["editor", "style"],
            project_key="alpha",
            thread_origin="thread-1",
        ),
    )
    created = _assert_json(created_response, 201)["created"]

    assert set(created) == {
        "memory_id",
        "principal_id",
        "label",
        "body",
        "kind",
        "keywords",
        "project_key",
        "thread_origin",
        "pin",
        "status",
        "revision",
        "stats",
        "bias",
        "embedding_model",
        "created_at",
        "updated_at",
    }
    assert created["principal_id"] == "owner"
    assert created["kind"] == "preference"
    assert created["keywords"] == ["editor", "style"]
    assert created["project_key"] == "alpha"
    assert created["thread_origin"] == "thread-1"
    assert created["status"] == "active"
    assert created["pin"] is False
    assert created["revision"] == 1
    assert created["stats"] == {
        "injections": 0,
        "removals": 0,
        "citations": 0,
        "never_kills": 0,
        "last_injected_at": None,
    }
    assert created["bias"] == pytest.approx(0.0)
    assert created["embedding_model"] == embedding_provider.model
    assert embedding_provider.calls == [("Original body",)]

    async with memory_session_factory() as session:
        root = (
            await session.scalars(
                select(MemoryRevision).where(MemoryRevision.memory_id == UUID(created["memory_id"]))
            )
        ).one()
    assert ULID_PATTERN.fullmatch(root.rev_uid)
    assert root.parent_uid is None
    assert root.revision == 1
    assert (root.body, root.label) == ("Original body", "Original label")
    assert (root.editor, root.origin_machine_id, root.reason) == (
        "test-editor",
        "test-machine",
        "",
    )

    collision_response = await memory_client.post(
        "/v1/memories",
        json=_create_body(
            label="Original label",
            body="token " * 129,
            force=True,
        ),
    )
    collision = _assert_json(collision_response, 409)
    assert collision == {
        "label_conflict": {
            "memory_id": created["memory_id"],
            "label": "Original label",
        }
    }
    assert embedding_provider.calls == [("Original body",)]


async def test_create_hard_duplicate_is_forced_but_scoped_to_principal(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
) -> None:
    embedding_provider.set("Source", basis_vector(0)).set("Other owner", basis_vector(0)).set(
        "Near copy", vector_with_cosine(0.96)
    )

    source = _assert_json(
        await memory_client.post(
            "/v1/memories",
            json=_create_body(label="Source", body="Source", project_key="alpha"),
        ),
        201,
    )["created"]
    other_owner = await memory_client.post(
        "/v1/memories",
        json=_create_body(
            principal_id="other-owner",
            label="Source",
            body="Other owner",
            project_key="alpha",
        ),
    )
    assert other_owner.status_code == 201

    duplicate_response = await memory_client.post(
        "/v1/memories",
        json=_create_body(
            label="Different label",
            body="Near copy",
            project_key="beta",
            force=True,
        ),
    )
    duplicate = _assert_json(duplicate_response, 409)
    card = duplicate["duplicate_of"]
    assert card == {
        "memory_id": source["memory_id"],
        "label": "Source",
        "body": "Source",
        "kind": "fact",
        "pin": False,
        "score": pytest.approx(0.96, abs=1e-5),
        "features": None,
        "rank": None,
    }


async def test_concurrent_same_principal_dedup_creates_only_one_root(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
) -> None:
    embedding_provider.set("Concurrent A", basis_vector(0)).set("Concurrent B", basis_vector(0))

    responses = await asyncio.gather(
        memory_client.post(
            "/v1/memories",
            json=_create_body(label="Concurrent A", body="Concurrent A"),
        ),
        memory_client.post(
            "/v1/memories",
            json=_create_body(label="Concurrent B", body="Concurrent B"),
        ),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    created_response = next(response for response in responses if response.status_code == 201)
    duplicate_response = next(response for response in responses if response.status_code == 409)
    created = _assert_json(created_response, 201)["created"]
    duplicate = _assert_json(duplicate_response, 409)["duplicate_of"]
    assert duplicate["memory_id"] == created["memory_id"]
    assert duplicate["score"] == pytest.approx(1.0, abs=1e-6)
    assert _assert_json(await memory_client.get("/v1/memories"), 200)["total"] == 1


async def test_create_similar_band_requires_force_retry(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
) -> None:
    lower_vector = vector_with_cosine(0.82)
    lower_vector[1] *= -1
    embedding_provider.set("Higher", vector_with_cosine(0.85)).set("Lower", lower_vector).set(
        "Candidate", basis_vector(0)
    )
    higher = _assert_json(
        await memory_client.post("/v1/memories", json=_create_body(label="Higher", body="Higher")),
        201,
    )["created"]
    lower = _assert_json(
        await memory_client.post("/v1/memories", json=_create_body(label="Lower", body="Lower")),
        201,
    )["created"]

    request = _create_body(label="Candidate", body="Candidate")
    similar_response = await memory_client.post("/v1/memories", json=request)
    similar = _assert_json(similar_response, 200)
    assert similar["created"] is None
    assert similar["similar"] == [
        {
            "memory_id": higher["memory_id"],
            "label": "Higher",
            "body": "Higher",
            "kind": "fact",
            "pin": False,
            "score": pytest.approx(0.85, abs=1e-5),
            "features": None,
            "rank": None,
        },
        {
            "memory_id": lower["memory_id"],
            "label": "Lower",
            "body": "Lower",
            "kind": "fact",
            "pin": False,
            "score": pytest.approx(0.82, abs=1e-5),
            "features": None,
            "rank": None,
        },
    ]

    before_retry = _assert_json(await memory_client.get("/v1/memories"), 200)
    assert before_retry["total"] == 2
    forced = _assert_json(
        await memory_client.post("/v1/memories", json=request | {"force": True}), 201
    )
    assert forced["created"]["label"] == "Candidate"
    assert _assert_json(await memory_client.get("/v1/memories"), 200)["total"] == 3


async def test_similar_equal_scores_break_ties_by_memory_id(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
) -> None:
    positive = vector_with_cosine(0.85)
    negative = list(positive)
    negative[1] *= -1
    embedding_provider.set("Positive", positive).set("Negative", negative).set(
        "Candidate", basis_vector(0)
    )

    positive_unit = _assert_json(
        await memory_client.post(
            "/v1/memories", json=_create_body(label="Positive", body="Positive")
        ),
        201,
    )["created"]
    negative_unit = _assert_json(
        await memory_client.post(
            "/v1/memories", json=_create_body(label="Negative", body="Negative")
        ),
        201,
    )["created"]

    similar = _assert_json(
        await memory_client.post(
            "/v1/memories", json=_create_body(label="Candidate", body="Candidate")
        ),
        200,
    )["similar"]
    expected_ids = sorted([positive_unit["memory_id"], negative_unit["memory_id"]])
    assert [card["memory_id"] for card in similar] == expected_ids
    assert [card["score"] for card in similar] == pytest.approx([0.85, 0.85], abs=1e-5)


async def test_patch_cas_reembeds_and_returns_exact_stale_conflict(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    embedding_provider.set("Before", basis_vector(0)).set("After", basis_vector(1)).set(
        "Stale body", basis_vector(2)
    )
    original = _assert_json(
        await memory_client.post(
            "/v1/memories", json=_create_body(label="Before label", body="Before")
        ),
        201,
    )["created"]
    memory_id = original["memory_id"]

    patched = _assert_json(
        await memory_client.patch(
            f"/v1/memories/{memory_id}",
            json=_patch_body(1, body="After", label="After label"),
        ),
        200,
    )
    assert patched["memory_id"] == memory_id
    assert (patched["body"], patched["label"], patched["revision"]) == (
        "After",
        "After label",
        2,
    )
    assert patched["embedding_model"] == embedding_provider.model
    assert datetime.fromisoformat(patched["updated_at"]) >= datetime.fromisoformat(
        original["updated_at"]
    )

    async with memory_session_factory() as session:
        stored = await session.get(MemoryUnit, UUID(memory_id))
        revisions = (
            await session.scalars(
                select(MemoryRevision)
                .where(MemoryRevision.memory_id == UUID(memory_id))
                .order_by(MemoryRevision.revision)
            )
        ).all()
    assert stored is not None
    assert stored.embedding[0] == pytest.approx(0.0, abs=1e-6)
    assert stored.embedding[1] == pytest.approx(1.0, abs=1e-6)
    assert [revision.revision for revision in revisions] == [1, 2]
    assert revisions[1].parent_uid == revisions[0].rev_uid
    assert (revisions[1].body, revisions[1].label) == ("After", "After label")
    assert (
        revisions[1].editor,
        revisions[1].origin_machine_id,
        revisions[1].reason,
    ) == ("patch-editor", "patch-machine", "test change")

    stale_response = await memory_client.patch(
        f"/v1/memories/{memory_id}",
        json=_patch_body(1, body="Stale body"),
    )
    stale = _assert_json(stale_response, 409)
    assert stale == {"conflict": patched}
    assert embedding_provider.calls == [("Before",), ("After",), ("Stale body",)]


async def test_patch_not_found_and_noop_are_problem_json(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
) -> None:
    missing_id = str(uuid4())
    missing = await memory_client.patch(
        f"/v1/memories/{missing_id}",
        json=_patch_body(1, body="Must not be embedded"),
    )
    _assert_problem(missing, 404, f"PATCH /v1/memories/{missing_id}")
    assert embedding_provider.calls == []

    noop_id = str(uuid4())
    noop = await memory_client.patch(
        f"/v1/memories/{noop_id}",
        json=_patch_body(
            1,
            body=None,
            label=None,
            keywords=None,
            kind=None,
            pin=None,
            status=None,
        ),
    )
    _assert_problem(noop, 422, f"PATCH /v1/memories/{noop_id}")


async def test_memory_limits_and_zero_vectors_fail_before_any_write(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    long_label = "L" * 65
    long_body = "token " * 129
    assert len(tiktoken.get_encoding("cl100k_base").encode(long_body)) > 128

    label_response = await memory_client.post(
        "/v1/memories", json=_create_body(label=long_label, body="Never embedded")
    )
    _assert_problem(label_response, 422, "POST /v1/memories")
    body_response = await memory_client.post(
        "/v1/memories", json=_create_body(label="Too long", body=long_body)
    )
    _assert_problem(body_response, 422, "POST /v1/memories")
    assert embedding_provider.calls == []

    embedding_provider.set("Valid", basis_vector(0)).set("Zero", [0.0] * 1536)
    valid = _assert_json(
        await memory_client.post("/v1/memories", json=_create_body(label="Valid", body="Valid")),
        201,
    )["created"]
    calls_after_valid_create = list(embedding_provider.calls)

    mixed_response = await memory_client.patch(
        f"/v1/memories/{valid['memory_id']}",
        json=_patch_body(1, body="Replacement", label=long_label),
    )
    _assert_problem(mixed_response, 422, f"PATCH /v1/memories/{valid['memory_id']}")
    assert embedding_provider.calls == calls_after_valid_create

    patch_response = await memory_client.patch(
        f"/v1/memories/{valid['memory_id']}", json=_patch_body(1, body=long_body)
    )
    _assert_problem(patch_response, 422, f"PATCH /v1/memories/{valid['memory_id']}")
    zero_response = await memory_client.post(
        "/v1/memories", json=_create_body(label="Zero", body="Zero")
    )
    _assert_problem(zero_response, 503, "POST /v1/memories")

    async with memory_session_factory() as session:
        stored = await session.get(MemoryUnit, UUID(valid["memory_id"]))
        total = await session.scalar(select(func.count()).select_from(MemoryUnit))
    assert stored is not None
    assert stored.revision == 1
    assert total == 1


async def test_patch_label_conflict_covers_reactivation_and_stale_precedence(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    embedding_provider.set("First", basis_vector(0)).set("Second", basis_vector(0)).set(
        "Third", basis_vector(2)
    )
    first = _assert_json(
        await memory_client.post("/v1/memories", json=_create_body(label="Shared", body="First")),
        201,
    )["created"]
    quarantined = _assert_json(
        await memory_client.patch(
            f"/v1/memories/{first['memory_id']}",
            json=_patch_body(1, status="quarantined"),
        ),
        200,
    )
    second = _assert_json(
        await memory_client.post("/v1/memories", json=_create_body(label="Shared", body="Second")),
        201,
    )["created"]

    reactivation_response = await memory_client.patch(
        f"/v1/memories/{first['memory_id']}",
        json=_patch_body(quarantined["revision"], status="active"),
    )
    assert _assert_json(reactivation_response, 409) == {
        "label_conflict": {
            "memory_id": second["memory_id"],
            "label": "Shared",
        }
    }

    third = _assert_json(
        await memory_client.post("/v1/memories", json=_create_body(label="Third", body="Third")),
        201,
    )["created"]
    stale_response = await memory_client.patch(
        f"/v1/memories/{third['memory_id']}",
        json=_patch_body(0, label="Shared"),
    )
    assert _assert_json(stale_response, 409) == {"conflict": third}

    label_response = await memory_client.patch(
        f"/v1/memories/{third['memory_id']}",
        json=_patch_body(1, label="Shared"),
    )
    assert _assert_json(label_response, 409) == {
        "label_conflict": {
            "memory_id": second["memory_id"],
            "label": "Shared",
        }
    }

    async with memory_session_factory() as session:
        first_head = await session.get(MemoryUnit, UUID(first["memory_id"]))
        third_head = await session.get(MemoryUnit, UUID(third["memory_id"]))
        first_history = await session.scalar(
            select(func.count())
            .select_from(MemoryRevision)
            .where(MemoryRevision.memory_id == UUID(first["memory_id"]))
        )
        third_history = await session.scalar(
            select(func.count())
            .select_from(MemoryRevision)
            .where(MemoryRevision.memory_id == UUID(third["memory_id"]))
        )
    assert first_head is not None
    assert (first_head.status, first_head.revision) == ("quarantined", 2)
    assert first_history == 2
    assert third_head is not None
    assert (third_head.label, third_head.revision) == ("Third", 1)
    assert third_history == 1


async def test_list_filters_total_paging_and_stable_order(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    embedding_provider.set("Alpha body", basis_vector(0)).set(
        "Body holds NeEdLe", basis_vector(1)
    ).set("Keyword only %_\\ marker", basis_vector(2))
    alpha = _assert_json(
        await memory_client.post(
            "/v1/memories",
            json=_create_body(
                label="Needle label",
                body="Alpha body",
                project_key="alpha",
            ),
        ),
        201,
    )["created"]
    quarantined = _assert_json(
        await memory_client.post(
            "/v1/memories",
            json=_create_body(
                label="Second",
                body="Body holds NeEdLe",
                project_key="alpha",
            ),
        ),
        201,
    )["created"]
    quarantined = _assert_json(
        await memory_client.patch(
            f"/v1/memories/{quarantined['memory_id']}",
            json=_patch_body(1, status="quarantined"),
        ),
        200,
    )
    beta = _assert_json(
        await memory_client.post(
            "/v1/memories",
            json=_create_body(
                label="Third",
                body="Keyword only %_\\ marker",
                keywords=["keyword-only-search-term"],
                project_key="beta",
            ),
        ),
        201,
    )["created"]

    tie_time = datetime(2025, 1, 1, tzinfo=UTC)
    latest_time = datetime(2025, 1, 2, tzinfo=UTC)
    tie_ids = [UUID(alpha["memory_id"]), UUID(quarantined["memory_id"])]
    async with memory_session_factory.begin() as session:
        await session.execute(
            update(MemoryUnit).where(MemoryUnit.id.in_(tie_ids)).values(updated_at=tie_time)
        )
        await session.execute(
            update(MemoryUnit)
            .where(MemoryUnit.id == UUID(beta["memory_id"]))
            .values(updated_at=latest_time)
        )

    page = _assert_json(
        await memory_client.get("/v1/memories", params={"limit": 2, "offset": 1}), 200
    )
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 1)
    assert [item["memory_id"] for item in page["items"]] == [
        str(memory_id) for memory_id in sorted(tie_ids)
    ]

    active_match = _assert_json(
        await memory_client.get(
            "/v1/memories",
            params={"project_key": "alpha", "status": "active", "q": "  NEEDLE  "},
        ),
        200,
    )
    assert active_match["total"] == 1
    assert [item["memory_id"] for item in active_match["items"]] == [alpha["memory_id"]]

    quarantined_match = _assert_json(
        await memory_client.get(
            "/v1/memories",
            params={"project_key": "alpha", "status": "quarantined", "q": "needle"},
        ),
        200,
    )
    assert quarantined_match["total"] == 1
    assert quarantined_match["items"][0]["memory_id"] == quarantined["memory_id"]

    filtered_page = _assert_json(
        await memory_client.get(
            "/v1/memories", params={"project_key": "alpha", "limit": 1, "offset": 1}
        ),
        200,
    )
    assert filtered_page["total"] == 2
    assert len(filtered_page["items"]) == 1
    assert filtered_page["items"][0]["memory_id"] == str(max(tie_ids))

    keyword_only = _assert_json(
        await memory_client.get("/v1/memories", params={"q": "keyword-only-search-term"}),
        200,
    )
    assert keyword_only["total"] == 0
    assert keyword_only["items"] == []

    literal = _assert_json(await memory_client.get("/v1/memories", params={"q": "%_\\"}), 200)
    assert [item["memory_id"] for item in literal["items"]] == [beta["memory_id"]]
    blank = _assert_json(await memory_client.get("/v1/memories", params={"q": "   "}), 200)
    assert blank["total"] == 3
