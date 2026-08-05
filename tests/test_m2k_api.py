"""Live-Postgres proofs for A-035 graph and scorer-console authority."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from conftest import basis_vector, vector_with_cosine
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import InjectionEvent, MemoryEdge, MemoryRevision, MemoryUnit
from spine.db.models import ScorerActivation as ScorerActivationRow
from spine.db.models import ScorerConfig as ScorerConfigRow


async def _insert_graph_fixture(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID]:
    first_id = UUID(int=9101)
    second_id = UUID(int=9102)
    now = datetime(2026, 8, 3, 12, tzinfo=UTC)
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                MemoryUnit(
                    id=first_id,
                    principal_id="owner",
                    label="Graph one",
                    body="First graph memory",
                    kind="fact",
                    keywords=["graph"],
                    embedding=basis_vector(0),
                    embedding_model="test-embedding-1536",
                    project_key=None,
                    thread_origin=None,
                    origin_path=None,
                    pin=True,
                    status="active",
                    revision=2,
                    stats={
                        "injections": 9,
                        "removals": 0,
                        "citations": 0,
                        "never_kills": 0,
                        "last_injected_at": None,
                    },
                    bias=0.0,
                    created_at=now,
                    updated_at=now + timedelta(minutes=2),
                ),
                MemoryUnit(
                    id=second_id,
                    principal_id="owner",
                    label="Graph two",
                    body="Second graph memory",
                    kind="preference",
                    keywords=["graph"],
                    embedding=vector_with_cosine(0.8),
                    embedding_model="test-embedding-1536",
                    project_key=None,
                    thread_origin=None,
                    origin_path=None,
                    pin=False,
                    status="quarantined",
                    revision=1,
                    stats={
                        "injections": 2,
                        "removals": 1,
                        "citations": 0,
                        "never_kills": 3,
                        "last_injected_at": None,
                    },
                    bias=-0.1,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                MemoryRevision(
                    rev_uid="01KZ4R00000000000000000001",
                    parent_uid=None,
                    memory_id=first_id,
                    revision=1,
                    body="First graph memory",
                    label="Graph one",
                    editor="user",
                    origin_machine_id="studio",
                    reason="create",
                    ts=now,
                ),
                MemoryRevision(
                    rev_uid="01KZ4R00000000000000000002",
                    parent_uid="01KZ4R00000000000000000001",
                    memory_id=first_id,
                    revision=2,
                    body="First graph memory",
                    label="Graph one",
                    editor="user",
                    origin_machine_id="studio",
                    reason="panel/edit",
                    ts=now + timedelta(minutes=2),
                ),
                MemoryRevision(
                    rev_uid="01KZ4R00000000000000000003",
                    parent_uid=None,
                    memory_id=second_id,
                    revision=1,
                    body="Second graph memory",
                    label="Graph two",
                    editor="user",
                    origin_machine_id="studio",
                    reason="create",
                    ts=now,
                ),
                MemoryEdge(
                    edge_uid="01KZ4R00000000000000000004",
                    from_memory_id=first_id,
                    to_memory_id=second_id,
                    edge_type="contradicts",
                    created_at=now,
                ),
            ]
        )
    return first_id, second_id


@pytest.mark.asyncio
async def test_memory_graph_uses_exact_encodings_and_current_membership(
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-035 is defended by verifying that memory graph uses exact encodings and current
    membership; this prevents drift in the authoritative graph, console, and accuracy
    boundary.
    """
    first_id, second_id = await _insert_graph_fixture(memory_session_factory)

    global_response = await memory_client.post(
        "/v1/memory-graph/query",
        json={"principal_id": "owner", "memory_ids": None},
    )
    current_response = await memory_client.post(
        "/v1/memory-graph/query",
        json={
            "principal_id": "owner",
            "memory_ids": [str(first_id), str(UUID(int=9999))],
        },
    )

    assert global_response.status_code == 200
    graph = global_response.json()
    assert graph["graph_edge_sim"] == 0.75
    assert [node["memory"]["memory_id"] for node in graph["nodes"]] == [
        str(first_id),
        str(second_id),
    ]
    first = graph["nodes"][0]
    assert first["memory"]["stats"]["injections"] == 9
    assert first["memory"]["pin"] is True
    assert [revision["revision"] for revision in first["revisions"]] == [1, 2]
    assert {
        (edge["kind"], edge["edge_type"], edge["revision_count"]) for edge in graph["edges"]
    } >= {
        ("similarity", None, None),
        ("lineage", "contradicts", None),
        ("edit_trail", None, 2),
    }
    assert current_response.status_code == 200
    current = current_response.json()
    assert len(current["nodes"]) == 1
    assert current["nodes"][0]["in_current_context"] is True
    assert current["omitted_memory_ids"] == [str(UUID(int=9999))]


@pytest.mark.asyncio
async def test_console_contributions_sum_exactly_and_control_inserts_a_version(
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-035/A-047 are defended by proving that contribution math, replay previews,
    content-addressed force, and the immutable activation journal share one authority.
    """
    thread_id = UUID(int=9201)
    memory_id = UUID(int=9202)
    async with memory_session_factory() as session, session.begin():
        session.add(
            InjectionEvent(
                event_uid="01KZ4R10000000000000000001",
                injection_id=UUID(int=9203),
                thread_id=thread_id,
                agent_id="general",
                machine_id="studio",
                principal_id="owner",
                project_key=None,
                agent_kind="general",
                prompt_text="console fixture",
                scorer_version="v0",
                memory_id=memory_id,
                memory_kind="fact",
                features={
                    "sem": 0.5,
                    "kw": 0.25,
                    "time": 1.0,
                    "proj": 0.5,
                    "freq": 0.0,
                    "hist": 0.5,
                    "_memory": {"label": "Console memory", "body": "Console body"},
                    "_prepare": {"model_context_tokens": 8192},
                },
                score=0.4,
                rank=1,
                shown_as="injected",
                actor_class="human",
                outcome="kept",
                ts=datetime(2026, 8, 3, 14, tzinfo=UTC),
            )
        )

    console = await memory_client.post(
        "/v1/scorer-console/query",
        json={
            "principal_id": "owner",
            "thread_id": str(thread_id),
            "as_of": "now",
        },
    )
    assert console.status_code == 200
    payload = console.json()
    assert payload["scope"] == "CURRENT"
    point = payload["candidates"][0]["points"][0]
    total = sum(Decimal(value) for value in point["contributions"].values())
    assert total == Decimal(point["score"])
    assert len(payload["descriptors"]) == 11

    values = payload["configurations"][0]["values"]
    values["tau"] = 0.6
    simulation = await memory_client.post(
        "/v1/scorer-simulations",
        json={
            "principal_id": "owner",
            "injection_id": str(UUID(int=9203)),
            "base_version": "v0",
            "values": values,
            "slice_parameter_id": "scorer.top_k",
        },
    )
    assert simulation.status_code == 200
    receipt = simulation.json()
    assert receipt["instant"]["status"] == "ready"
    assert len(receipt["slice"]["points"]) == 8
    event_uid = "01KZ4R10000000000000000002"
    request = {
        "event_uid": event_uid,
        "base_version": "v0",
        "values": values,
        "simulation_digest": receipt["simulation_digest"],
        "force": True,
        "actor_class": "human",
        "machine_id": "studio",
    }
    stale = await memory_client.post(
        "/v1/scorer-configs",
        json={**request, "simulation_digest": "0" * 64},
    )
    created = await memory_client.post("/v1/scorer-configs", json=request)
    replay = await memory_client.post("/v1/scorer-configs", json=request)

    assert stale.status_code == 409
    assert stale.json()["detail"] == "M2K operation refused: simulation_stale."
    assert created.status_code == 200
    assert replay.status_code == 200
    assert created.json()["version"] == f"m2k-{event_uid}"
    assert created.json()["status"] == "active"
    async with memory_session_factory() as session:
        active = (
            (await session.execute(select(ScorerConfigRow).where(ScorerConfigRow.active.is_(True))))
            .scalars()
            .one()
        )
        activations = (await session.execute(select(ScorerActivationRow))).scalars().all()
    assert active.version == f"m2k-{event_uid}"
    assert len(activations) == 1
    assert activations[0].changes["scorer.tau"] == {"old": 0.55, "new": 0.6}
    assert activations[0].changes["_force"] == {
        "simulation_digest": receipt["simulation_digest"],
        "source_boundary": "01KZ4R10000000000000000001",
        "holdout_dispositions": 0,
        "incumbent_accuracy_percent": None,
        "accuracy_percent": None,
        "delta_percent": None,
    }


@pytest.mark.asyncio
async def test_only_learner_proposals_can_be_activated_and_accuracy_is_measured(
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-035/A-047 are defended by proving that audition is read-only and only a
    subsequent explicit activation can replace the incumbent scorer.
    """
    injection_id = UUID(int=9301)
    memory_id = UUID(int=9302)
    async with memory_session_factory() as session, session.begin():
        base = await session.get(ScorerConfigRow, "v0")
        assert base is not None
        params = dict(base.params)
        params["_learner"] = {
            "status": "proposed",
            "holdout_dispositions": 10,
            "replay": {
                "incumbent": {"disagreements": 3},
                "challenger": {"disagreements": 1},
            },
        }
        session.add(
            ScorerConfigRow(
                version="learner-proposal",
                weights=dict(base.weights),
                params=params,
                active=False,
            )
        )
        session.add(
            InjectionEvent(
                event_uid="01KZ4R20000000000000000000",
                injection_id=injection_id,
                thread_id=UUID(int=9303),
                agent_id="general",
                machine_id="studio",
                principal_id="owner",
                project_key=None,
                agent_kind="general",
                prompt_text="audition fixture",
                scorer_version="v0",
                memory_id=memory_id,
                memory_kind="fact",
                features={
                    "sem": 0.5,
                    "kw": 0.25,
                    "time": 1.0,
                    "proj": 0.5,
                    "freq": 0.0,
                    "hist": 0.5,
                    "_memory": {"label": "Audition memory", "body": "Audition body"},
                    "_prepare": {"model_context_tokens": 8192},
                },
                score=0.4,
                rank=1,
                shown_as="injected",
                actor_class="human",
                outcome=None,
                ts=datetime(2026, 8, 3, 15, tzinfo=UTC),
            )
        )

    before = await memory_client.post(
        "/v1/scorer-console/query",
        json={"principal_id": "owner", "thread_id": None, "as_of": "now"},
    )
    assert before.status_code == 200
    accuracy = {item["version"]: item for item in before.json()["accuracy"]}
    assert accuracy["learner-proposal"]["accuracy_percent"] == "90"

    audition = await memory_client.post(
        "/v1/scorer-auditions",
        json={
            "principal_id": "owner",
            "injection_id": str(injection_id),
            "proposal_version": "learner-proposal",
        },
    )
    assert audition.status_code == 200
    assert audition.json()["instant"]["status"] == "ready"
    async with memory_session_factory() as session:
        incumbent = (
            (await session.execute(select(ScorerConfigRow).where(ScorerConfigRow.active.is_(True))))
            .scalars()
            .one()
        )
    assert incumbent.version == "v0"

    activated = await memory_client.post(
        "/v1/scorer-configs/learner-proposal/activate",
        json={
            "event_uid": "01KZ4R20000000000000000001",
            "actor_class": "human",
            "machine_id": "studio",
        },
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
