"""Live-Postgres contracts for A-053's append-only hygiene overlay."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from spine.db.models import InjectionEvent, InjectionEventAnnotation
from spine.learner.locking import LEARNER_ADVISORY_LOCK_KEY


def _event_uid(seed: int) -> str:
    return f"01KZ{seed:022d}"


def _event(seed: int, *, principal_id: str, machine_id: str) -> InjectionEvent:
    return InjectionEvent(
        event_uid=_event_uid(seed),
        injection_id=UUID(int=1000 + seed),
        thread_id=UUID(int=2000 + seed),
        agent_id="general",
        machine_id=machine_id,
        principal_id=principal_id,
        project_key=None,
        agent_kind="general",
        prompt_text="A-053 annotation target",
        scorer_version="v0",
        memory_id=UUID(int=3000 + seed),
        memory_kind="fact",
        features={},
        score=0.5,
        rank=1,
        shown_as="injected",
        actor_class="human",
        outcome="kept",
        ts=datetime(2026, 8, 10, seed, tzinfo=UTC),
    )


def _annotation(
    seed: int,
    *,
    principal_id: str,
    machine_id: str,
    reason: str = "F033 exact verification correlation",
) -> dict[str, str]:
    return {
        "target_event_uid": _event_uid(seed),
        "expected_principal_id": principal_id,
        "expected_machine_id": machine_id,
        "reason": reason,
        "annotator_principal_id": "m2za-sop-verification",
        "annotator_machine_id": "m2za-sop-verification",
        "annotator_origin_agent": "verification:m2za",
    }


async def _wait_for_annotation_lock_waiter(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    for _ in range(200):
        async with session_factory() as session:
            waiting = await session.scalar(
                text(
                    "SELECT count(*) FROM pg_locks "
                    "WHERE locktype = 'advisory' AND classid = 0 "
                    "AND objid = :key AND NOT granted"
                ),
                {"key": LEARNER_ADVISORY_LOCK_KEY},
            )
        if waiting == 1:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("annotation write never waited for the learner advisory lock")


@pytest.mark.asyncio
async def test_annotation_batch_is_atomic_idempotent_and_fingerprint_guarded(
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-053/F033 defend atomic guarded annotations so cleanup cannot rewrite owner evidence."""

    identities = {
        1: ("d1-owner", "d1-relay"),
        2: ("nocturne-deploy-verify-run", "nocturne-deploy"),
        3: ("owner-three", "studio-three"),
        4: ("owner-four", "studio-four"),
    }
    async with memory_session_factory() as session, session.begin():
        session.add_all(
            [
                _event(seed, principal_id=principal, machine_id=machine)
                for seed, (principal, machine) in identities.items()
            ]
        )

    first_items = [
        _annotation(seed, principal_id=principal, machine_id=machine)
        for seed, (principal, machine) in list(identities.items())[:2]
    ]
    first = await memory_client.post(
        "/v1/injection-event-annotations",
        json={"annotations": first_items},
    )
    assert first.status_code == 200
    assert first.json() == {"accepted": 2}
    async with memory_session_factory() as session:
        stored = (
            (
                await session.execute(
                    select(InjectionEventAnnotation).order_by(
                        InjectionEventAnnotation.target_event_uid
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(stored) == 2
    assert [row.kind for row in stored] == ["verification_only", "verification_only"]
    assert [row.target_principal_id for row in stored] == [
        identities[1][0],
        identities[2][0],
    ]
    assert [row.target_machine_id for row in stored] == [
        identities[1][1],
        identities[2][1],
    ]
    assert all(row.ts.tzinfo is not None for row in stored)
    assert stored[0].reason == "F033 exact verification correlation"
    assert stored[0].annotator_principal_id == "m2za-sop-verification"
    assert stored[0].annotator_machine_id == "m2za-sop-verification"
    assert stored[0].annotator_origin_agent == "verification:m2za"
    first_timestamps = [row.ts for row in stored]
    replay = await memory_client.post(
        "/v1/injection-event-annotations",
        json={"annotations": first_items},
    )
    assert replay.status_code == 200
    assert replay.json() == {"accepted": 2}
    async with memory_session_factory() as session:
        replayed = (
            (
                await session.execute(
                    select(InjectionEventAnnotation).order_by(
                        InjectionEventAnnotation.target_event_uid
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(replayed) == 2
    assert [row.ts for row in replayed] == first_timestamps

    conflict = await memory_client.post(
        "/v1/injection-event-annotations",
        json={
            "annotations": [
                _annotation(3, principal_id=identities[3][0], machine_id=identities[3][1]),
                _annotation(
                    1,
                    principal_id=identities[1][0],
                    machine_id=identities[1][1],
                    reason="different immutable reason",
                ),
            ]
        },
    )
    replay_field_conflicts = []
    for field, value in (
        ("annotator_principal_id", "different-principal"),
        ("annotator_machine_id", "different-machine"),
        ("annotator_origin_agent", "different:origin"),
    ):
        changed_replay = _annotation(
            1,
            principal_id=identities[1][0],
            machine_id=identities[1][1],
        )
        changed_replay[field] = value
        replay_field_conflicts.append(
            await memory_client.post(
                "/v1/injection-event-annotations",
                json={
                    "annotations": [
                        _annotation(
                            3,
                            principal_id=identities[3][0],
                            machine_id=identities[3][1],
                        ),
                        changed_replay,
                    ]
                },
            )
        )
    principal_mismatch = await memory_client.post(
        "/v1/injection-event-annotations",
        json={
            "annotations": [
                _annotation(3, principal_id=identities[3][0], machine_id=identities[3][1]),
                _annotation(4, principal_id="wrong-principal", machine_id=identities[4][1]),
            ]
        },
    )
    machine_mismatch = await memory_client.post(
        "/v1/injection-event-annotations",
        json={
            "annotations": [
                _annotation(3, principal_id=identities[3][0], machine_id=identities[3][1]),
                _annotation(4, principal_id=identities[4][0], machine_id="wrong-machine"),
            ]
        },
    )
    missing = await memory_client.post(
        "/v1/injection-event-annotations",
        json={
            "annotations": [
                _annotation(3, principal_id=identities[3][0], machine_id=identities[3][1]),
                _annotation(99, principal_id="missing", machine_id="missing"),
            ]
        },
    )

    assert conflict.status_code == 409
    assert [response.status_code for response in replay_field_conflicts] == [409, 409, 409]
    assert principal_mismatch.status_code == 409
    assert machine_mismatch.status_code == 409
    assert missing.status_code == 404
    async with memory_session_factory() as session:
        after = (
            (
                await session.execute(
                    select(InjectionEventAnnotation).order_by(
                        InjectionEventAnnotation.target_event_uid
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(after) == 2
    assert [row.ts for row in after] == first_timestamps


@pytest.mark.asyncio
async def test_annotation_contract_rejects_malformed_oversized_or_client_authored_fields(
    memory_client: AsyncClient,
) -> None:
    """A-053/F033 bound caller fields; the server owns kind, timestamp, and target copies."""

    valid = _annotation(1, principal_id="owner", machine_id="studio")
    cases = [
        {"annotations": []},
        {
            "annotations": [
                valid,
                {**valid, "target_event_uid": valid["target_event_uid"].lower()},
            ]
        },
        {"annotations": [{**valid, "target_event_uid": "not-a-ulid"}]},
        {"annotations": [{**valid, "reason": " "}]},
        {"annotations": [{**valid, "kind": "verification_only"}]},
        {"annotations": [{**valid, "ts": "2026-08-10T00:00:00Z"}]},
        {"annotations": [{**valid, "target_event_uid": _event_uid(seed)} for seed in range(101)]},
    ]

    for body in cases:
        response = await memory_client.post("/v1/injection-event-annotations", json=body)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_annotation_rows_are_database_enforced_append_only(
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-053/F033 defend original classification history against UPDATE and DELETE."""

    async with memory_session_factory() as session, session.begin():
        session.add(_event(1, principal_id="owner", machine_id="studio"))
    response = await memory_client.post(
        "/v1/injection-event-annotations",
        json={"annotations": [_annotation(1, principal_id="owner", machine_id="studio")]},
    )
    assert response.status_code == 200

    async with memory_session_factory() as session:
        with pytest.raises(DBAPIError, match="injection_event_annotation is append-only"):
            async with session.begin():
                await session.execute(
                    update(InjectionEventAnnotation)
                    .where(InjectionEventAnnotation.target_event_uid == _event_uid(1))
                    .values(reason="rewritten")
                )
    async with memory_session_factory() as session:
        with pytest.raises(DBAPIError, match="injection_event_annotation is append-only"):
            async with session.begin():
                row = await session.get(InjectionEventAnnotation, _event_uid(1))
                assert row is not None
                await session.delete(row)
                await session.flush()
    async with memory_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(InjectionEventAnnotation)) == 1


@pytest.mark.asyncio
async def test_annotation_write_waits_for_the_learner_evidence_lock(
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-053/A-051 serialize annotations with whole-log learner snapshots."""

    async with memory_session_factory() as session, session.begin():
        session.add(_event(1, principal_id="owner", machine_id="studio"))
    engine = memory_session_factory.kw.get("bind")
    assert isinstance(engine, AsyncEngine)
    async with engine.connect() as connection:
        await connection.execute(
            text("SELECT pg_advisory_lock(:key)"),
            {"key": LEARNER_ADVISORY_LOCK_KEY},
        )
        await connection.commit()
        request = asyncio.create_task(
            memory_client.post(
                "/v1/injection-event-annotations",
                json={"annotations": [_annotation(1, principal_id="owner", machine_id="studio")]},
            )
        )
        await _wait_for_annotation_lock_waiter(memory_session_factory)
        assert not request.done()
        released = await connection.scalar(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": LEARNER_ADVISORY_LOCK_KEY},
        )
        await connection.commit()
        assert released is True
        response = await asyncio.wait_for(request, timeout=2)

    assert response.status_code == 200
    assert response.json() == {"accepted": 1}
