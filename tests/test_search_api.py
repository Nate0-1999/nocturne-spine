"""S6 live-Postgres proofs for deterministic semantic search."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from conftest import ScriptedEmbeddingProvider, basis_vector, vector_with_cosine
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import MemoryRevision, MemoryUnit
from spine.ids import mint_ulid

DEFAULT_STATS = {
    "injections": 0,
    "removals": 0,
    "citations": 0,
    "never_kills": 0,
    "last_injected_at": None,
}
CARD_FIELDS = {"memory_id", "label", "body", "kind", "pin", "score", "features", "rank"}


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryFixture:
    memory_id: UUID
    label: str
    cosine: float
    principal_id: str = "owner"
    project_key: str | None = None
    status: str = "active"
    pin: bool = False
    kind: str = "fact"
    bias: float = 0.0


async def _insert_memories(
    session_factory: async_sessionmaker[AsyncSession],
    fixtures: list[MemoryFixture],
) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    async with session_factory() as session:
        async with session.begin():
            for item in fixtures:
                session.add(
                    MemoryUnit(
                        id=item.memory_id,
                        principal_id=item.principal_id,
                        label=item.label,
                        body=f"{item.label} body",
                        kind=item.kind,
                        keywords=[],
                        embedding=vector_with_cosine(item.cosine),
                        embedding_model="test-embedding-1536",
                        project_key=item.project_key,
                        thread_origin=None,
                        origin_path=None,
                        pin=item.pin,
                        status=item.status,
                        revision=1,
                        stats=dict(DEFAULT_STATS),
                        bias=item.bias,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
            await session.flush()
            for item in fixtures:
                session.add(
                    MemoryRevision(
                        rev_uid=mint_ulid(),
                        parent_uid=None,
                        memory_id=item.memory_id,
                        revision=1,
                        body=f"{item.label} body",
                        label=item.label,
                        editor="fixture",
                        origin_machine_id="fixture-machine",
                        reason="fixture root",
                        ts=timestamp,
                    )
                )


def _assert_problem(response: Response, status: int) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].split(";", 1)[0] == "application/problem+json"
    problem = response.json()
    assert problem["type"] == "about:blank"
    assert problem["status"] == status
    assert problem["endpoint"] == "POST /v1/search"
    return problem


async def test_search_uses_raw_cosine_and_exact_principal_status_project_filters(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    query = "alpha context"
    embedding_provider.set(query, basis_vector(0))
    fixtures = [
        MemoryFixture(memory_id=UUID(int=101), label="Global", cosine=0.8),
        MemoryFixture(memory_id=UUID(int=102), label="Alpha", cosine=0.7, project_key="alpha"),
        MemoryFixture(memory_id=UUID(int=103), label="Pinned", cosine=0.6, pin=True),
        MemoryFixture(
            memory_id=UUID(int=104),
            label="Negative",
            cosine=-0.2,
            project_key="alpha",
            kind="preference",
            bias=100.0,
        ),
        MemoryFixture(
            memory_id=UUID(int=105), label="Other project", cosine=1.0, project_key="beta"
        ),
        MemoryFixture(
            memory_id=UUID(int=106),
            label="Other principal",
            cosine=1.0,
            principal_id="someone-else",
            project_key="alpha",
        ),
        MemoryFixture(
            memory_id=UUID(int=107),
            label="Quarantined",
            cosine=1.0,
            project_key="alpha",
            status="quarantined",
        ),
        MemoryFixture(memory_id=UUID(int=108), label="Tombstoned", cosine=1.0, status="tombstoned"),
    ]
    await _insert_memories(memory_session_factory, fixtures)

    response = await memory_client.post(
        "/v1/search",
        json={"principal_id": "owner", "query": query, "k": 50, "project_key": "alpha"},
    )

    assert response.status_code == 200
    cards = response.json()["results"]
    assert [card["memory_id"] for card in cards] == [
        str(UUID(int=value)) for value in range(101, 105)
    ]
    assert [card["score"] for card in cards] == pytest.approx([0.8, 0.7, 0.6, -0.2])
    assert all(set(card) == CARD_FIELDS for card in cards)
    assert all(card["features"] is None and card["rank"] is None for card in cards)
    assert [card["pin"] for card in cards] == [False, False, True, False]
    assert cards[-1]["kind"] == "preference"
    assert embedding_provider.calls == [(query,)]


async def test_search_omitted_and_null_project_are_principal_wide(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    query = "all project contexts"
    embedding_provider.set(query, basis_vector(0))
    await _insert_memories(
        memory_session_factory,
        [
            MemoryFixture(memory_id=UUID(int=201), label="Beta", cosine=0.9, project_key="beta"),
            MemoryFixture(memory_id=UUID(int=202), label="Global", cosine=0.6),
            MemoryFixture(memory_id=UUID(int=203), label="Alpha", cosine=0.3, project_key="alpha"),
        ],
    )
    request = {"principal_id": "owner", "query": query, "k": 50}

    omitted = await memory_client.post("/v1/search", json=request)
    explicit_null = await memory_client.post("/v1/search", json={**request, "project_key": None})
    alpha = await memory_client.post("/v1/search", json={**request, "project_key": "alpha"})

    assert omitted.status_code == explicit_null.status_code == alpha.status_code == 200
    assert omitted.json() == explicit_null.json()
    assert [card["memory_id"] for card in omitted.json()["results"]] == [
        str(UUID(int=201)),
        str(UUID(int=202)),
        str(UUID(int=203)),
    ]
    assert [card["memory_id"] for card in alpha.json()["results"]] == [
        str(UUID(int=202)),
        str(UUID(int=203)),
    ]
    assert embedding_provider.calls == [(query,), (query,), (query,)]


async def test_search_default_k_has_uuid_cutoff_and_invalid_k_does_not_embed(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    query = "equal candidates"
    embedding_provider.set(query, basis_vector(0))
    await _insert_memories(
        memory_session_factory,
        [
            MemoryFixture(memory_id=UUID(int=value), label=f"Tie {value}", cosine=0.5)
            for value in range(311, 300, -1)
        ],
    )

    response = await memory_client.post(
        "/v1/search",
        json={"principal_id": "owner", "query": query},
    )

    assert response.status_code == 200
    assert [card["memory_id"] for card in response.json()["results"]] == [
        str(UUID(int=value)) for value in range(301, 311)
    ]
    one = await memory_client.post(
        "/v1/search",
        json={"principal_id": "owner", "query": query, "k": 1},
    )
    assert one.status_code == 200
    assert [card["memory_id"] for card in one.json()["results"]] == [str(UUID(int=301))]
    for invalid in (0, 51, True):
        _assert_problem(
            await memory_client.post(
                "/v1/search",
                json={"principal_id": "owner", "query": query, "k": invalid},
            ),
            422,
        )
    assert embedding_provider.calls == [(query,), (query,)]


async def test_search_empty_and_invalid_provider_vector_have_exact_responses(
    memory_client: AsyncClient,
    embedding_provider: ScriptedEmbeddingProvider,
) -> None:
    valid_query, invalid_query = "nothing here", "zero vector"
    embedding_provider.set(valid_query, basis_vector(0)).set(invalid_query, [0.0] * 1536)

    empty = await memory_client.post(
        "/v1/search",
        json={"principal_id": "owner", "query": valid_query},
    )
    unavailable = await memory_client.post(
        "/v1/search",
        json={"principal_id": "owner", "query": invalid_query},
    )

    assert empty.status_code == 200
    assert empty.json() == {"results": []}
    problem = _assert_problem(unavailable, 503)
    assert problem["detail"] == "The embedding provider could not complete the request."
    assert embedding_provider.calls == [(valid_query,), (invalid_query,)]
