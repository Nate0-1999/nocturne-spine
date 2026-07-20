"""S1 proofs for literal C.2 mappings, CAS history, and tombstones."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, func, insert, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateTable

from spine.db.memory import (
    CasUpdate,
    MemoryCasConflictError,
    MemoryLineageError,
    MemoryUnitChanges,
    MemoryUnitSnapshot,
    cas_update_memory_unit,
    tombstone_memory_unit,
)
from spine.db.models import Base, MemoryRevision, MemoryUnit
from spine.db.session import make_session_factory

ZERO_EMBEDDING = (0.0,) * 1536
SEEDED_AT = datetime(2020, 1, 1, tzinfo=UTC)


@pytest.fixture
async def database(
    migrated_database_url: str,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(migrated_database_url)
    try:
        yield engine, make_session_factory(engine)
    finally:
        await engine.dispose()


def _rev_uid(value: int) -> str:
    """Return a deterministic 26-character Crockford-compatible test ULID."""

    return f"{value:026d}"


async def _insert_memory_and_root(
    session: AsyncSession,
    *,
    memory_id: UUID,
    root_uid: str,
    principal_id: str,
    label: str,
    body: str,
) -> None:
    await session.execute(
        insert(MemoryUnit).values(
            id=memory_id,
            principal_id=principal_id,
            label=label,
            body=body,
            kind="fact",
            embedding=list(ZERO_EMBEDDING),
            embedding_model="s1-test",
            created_at=SEEDED_AT,
            updated_at=SEEDED_AT,
        )
    )
    await session.execute(
        insert(MemoryRevision).values(
            rev_uid=root_uid,
            parent_uid=None,
            memory_id=memory_id,
            revision=1,
            body=body,
            label=label,
            editor="user",
            origin_machine_id="machine-root",
            reason="create",
        )
    )


async def _seed_memory(
    sessions: async_sessionmaker[AsyncSession],
    *,
    memory_id: UUID,
    root_uid: str,
    principal_id: str,
    label: str,
    body: str = "root body",
) -> None:
    async with sessions.begin() as session:
        await _insert_memory_and_root(
            session,
            memory_id=memory_id,
            root_uid=root_uid,
            principal_id=principal_id,
            label=label,
            body=body,
        )


async def test_models_match_authoritative_c2_schema(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    engine, _ = database

    def schema_diff(connection: Any) -> list[Any]:
        context = MigrationContext.configure(
            connection,
            opts={"compare_type": True, "compare_server_default": True},
        )
        return compare_metadata(context, Base.metadata)

    async with engine.connect() as connection:
        differences = await connection.run_sync(schema_diff)

    assert differences == []
    assert tuple(Base.metadata.tables) == (
        "memory_unit",
        "memory_revision",
        "thread",
        "injection_event",
        "scorer_config",
    )

    expected_columns = {
        "memory_unit": (
            "id",
            "principal_id",
            "label",
            "body",
            "kind",
            "keywords",
            "embedding",
            "embedding_model",
            "project_key",
            "thread_origin",
            "origin_path",
            "pin",
            "status",
            "revision",
            "stats",
            "bias",
            "created_at",
            "updated_at",
        ),
        "memory_revision": (
            "rev_uid",
            "parent_uid",
            "memory_id",
            "revision",
            "body",
            "label",
            "editor",
            "origin_machine_id",
            "reason",
            "ts",
        ),
        "thread": (
            "id",
            "principal_id",
            "agent_id",
            "machine_id",
            "project_key",
            "snapshot_ts",
            "created_at",
        ),
        "injection_event": (
            "id",
            "event_uid",
            "injection_id",
            "thread_id",
            "agent_id",
            "machine_id",
            "principal_id",
            "project_key",
            "agent_kind",
            "prompt_text",
            "scorer_version",
            "memory_id",
            "memory_kind",
            "features",
            "score",
            "rank",
            "shown_as",
            "outcome",
            "ts",
        ),
        "scorer_config": ("version", "weights", "params", "created_at", "active"),
    }
    assert {
        name: tuple(table.c.keys()) for name, table in Base.metadata.tables.items()
    } == expected_columns

    nullable = {
        name: {column.name for column in table.c if column.nullable}
        for name, table in Base.metadata.tables.items()
    }
    assert nullable == {
        "memory_unit": {"project_key", "thread_origin", "origin_path"},
        "memory_revision": {"parent_uid", "revision"},
        "thread": {"project_key", "snapshot_ts"},
        "injection_event": {"project_key", "outcome"},
        "scorer_config": set(),
    }

    primary_keys = {
        name: tuple(column.name for column in table.primary_key.columns)
        for name, table in Base.metadata.tables.items()
    }
    assert primary_keys == {
        "memory_unit": ("id",),
        "memory_revision": ("rev_uid",),
        "thread": ("id",),
        "injection_event": ("id",),
        "scorer_config": ("version",),
    }

    dialect = postgresql.dialect()
    types = {
        f"{name}.{column.name}": column.type.compile(dialect=dialect)
        for name, table in Base.metadata.tables.items()
        for column in table.c
    }
    assert types == {
        "memory_unit.id": "UUID",
        "memory_unit.principal_id": "TEXT",
        "memory_unit.label": "TEXT",
        "memory_unit.body": "TEXT",
        "memory_unit.kind": "TEXT",
        "memory_unit.keywords": "TEXT[]",
        "memory_unit.embedding": "VECTOR(1536)",
        "memory_unit.embedding_model": "TEXT",
        "memory_unit.project_key": "TEXT",
        "memory_unit.thread_origin": "TEXT",
        "memory_unit.origin_path": "TEXT",
        "memory_unit.pin": "BOOLEAN",
        "memory_unit.status": "TEXT",
        "memory_unit.revision": "INTEGER",
        "memory_unit.stats": "JSONB",
        "memory_unit.bias": "REAL",
        "memory_unit.created_at": "TIMESTAMP WITH TIME ZONE",
        "memory_unit.updated_at": "TIMESTAMP WITH TIME ZONE",
        "memory_revision.rev_uid": "TEXT",
        "memory_revision.parent_uid": "TEXT",
        "memory_revision.memory_id": "UUID",
        "memory_revision.revision": "INTEGER",
        "memory_revision.body": "TEXT",
        "memory_revision.label": "TEXT",
        "memory_revision.editor": "TEXT",
        "memory_revision.origin_machine_id": "TEXT",
        "memory_revision.reason": "TEXT",
        "memory_revision.ts": "TIMESTAMP WITH TIME ZONE",
        "thread.id": "UUID",
        "thread.principal_id": "TEXT",
        "thread.agent_id": "TEXT",
        "thread.machine_id": "TEXT",
        "thread.project_key": "TEXT",
        "thread.snapshot_ts": "TIMESTAMP WITH TIME ZONE",
        "thread.created_at": "TIMESTAMP WITH TIME ZONE",
        "injection_event.id": "BIGINT",
        "injection_event.event_uid": "TEXT",
        "injection_event.injection_id": "UUID",
        "injection_event.thread_id": "UUID",
        "injection_event.agent_id": "TEXT",
        "injection_event.machine_id": "TEXT",
        "injection_event.principal_id": "TEXT",
        "injection_event.project_key": "TEXT",
        "injection_event.agent_kind": "TEXT",
        "injection_event.prompt_text": "TEXT",
        "injection_event.scorer_version": "TEXT",
        "injection_event.memory_id": "UUID",
        "injection_event.memory_kind": "TEXT",
        "injection_event.features": "JSONB",
        "injection_event.score": "REAL",
        "injection_event.rank": "INTEGER",
        "injection_event.shown_as": "TEXT",
        "injection_event.outcome": "TEXT",
        "injection_event.ts": "TIMESTAMP WITH TIME ZONE",
        "scorer_config.version": "TEXT",
        "scorer_config.weights": "JSONB",
        "scorer_config.params": "JSONB",
        "scorer_config.created_at": "TIMESTAMP WITH TIME ZONE",
        "scorer_config.active": "BOOLEAN",
    }

    defaults = {
        f"{name}.{column.name}": str(column.server_default.arg.compile(dialect=dialect))
        for name, table in Base.metadata.tables.items()
        for column in table.c
        if column.server_default is not None
    }
    assert defaults == {
        "memory_unit.id": "gen_random_uuid()",
        "memory_unit.keywords": "'{}'",
        "memory_unit.pin": "false",
        "memory_unit.status": "'active'",
        "memory_unit.revision": "1",
        "memory_unit.stats": (
            '\'{"injections":0,"removals":0,"citations":0,'
            '"never_kills":0,"last_injected_at":null}\'::jsonb'
        ),
        "memory_unit.bias": "0.0",
        "memory_unit.created_at": "now()",
        "memory_unit.updated_at": "now()",
        "memory_revision.reason": "''",
        "memory_revision.ts": "now()",
        "thread.created_at": "now()",
        "injection_event.agent_kind": "'general'",
        "injection_event.ts": "now()",
        "scorer_config.created_at": "now()",
        "scorer_config.active": "false",
    }
    memory_unit_ddl = str(CreateTable(Base.metadata.tables["memory_unit"]).compile(dialect=dialect))
    assert (
        "stats JSONB DEFAULT "
        '\'{"injections":0,"removals":0,"citations":0,'
        '"never_kills":0,"last_injected_at":null}\'::jsonb NOT NULL' in memory_unit_ddl
    )

    checks = {
        name: {
            constraint.name: str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
        for name, table in Base.metadata.tables.items()
    }
    assert checks == {
        "memory_unit": {
            "memory_unit_kind_check": (
                "kind IN ('fact','preference','procedure','project_note','persona','pinned')"
            ),
            "memory_unit_status_check": ("status IN ('active','quarantined','tombstoned')"),
        },
        "memory_revision": {},
        "thread": {},
        "injection_event": {
            "injection_event_shown_as_check": ("shown_as IN ('injected','near_miss','pinned')")
        },
        "scorer_config": {},
    }

    unit = Base.metadata.tables["memory_unit"]
    indexes = {index.name: index for index in unit.indexes}
    assert set(indexes) == {
        "memory_unit_embedding_idx",
        "memory_unit_principal_id_status_project_key_idx",
        "memory_unit_active_label",
    }
    assert indexes["memory_unit_embedding_idx"].dialect_options["postgresql"]["using"] == "hnsw"
    assert indexes["memory_unit_embedding_idx"].dialect_options["postgresql"]["ops"] == {
        "embedding": "vector_cosine_ops"
    }
    assert indexes["memory_unit_active_label"].unique is True
    assert (
        str(indexes["memory_unit_active_label"].dialect_options["postgresql"]["where"])
        == "status = 'active'"
    )

    revision = Base.metadata.tables["memory_revision"]
    assert {foreign_key.target_fullname for foreign_key in revision.c.parent_uid.foreign_keys} == {
        "memory_revision.rev_uid"
    }
    assert {foreign_key.target_fullname for foreign_key in revision.c.memory_id.foreign_keys} == {
        "memory_unit.id"
    }


async def test_cas_updates_form_cloud_head_lineage(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = database
    memory_id = uuid4()
    root_uid, child_uid, grandchild_uid = (_rev_uid(value) for value in (101, 102, 103))
    await _seed_memory(
        sessions,
        memory_id=memory_id,
        root_uid=root_uid,
        principal_id=f"lineage-{memory_id}",
        label="original label",
    )

    async with sessions.begin() as session:
        child = await cas_update_memory_unit(
            session,
            CasUpdate(
                memory_id=memory_id,
                expected_revision=1,
                rev_uid=child_uid,
                editor="agent:writer",
                origin_machine_id="machine-child",
                reason="body correction",
                changes=MemoryUnitChanges(
                    body="child body",
                    origin_path="src/spine/db",
                ),
            ),
        )
    async with sessions.begin() as session:
        grandchild = await cas_update_memory_unit(
            session,
            CasUpdate(
                memory_id=memory_id,
                expected_revision=2,
                rev_uid=grandchild_uid,
                editor="user",
                origin_machine_id="machine-grandchild",
                reason="rename",
                changes=MemoryUnitChanges(label="renamed label"),
            ),
        )

    assert child.revision == 2
    assert child.body == "child body"
    assert child.label == "original label"
    assert child.origin_path == "src/spine/db"
    assert grandchild.revision == 3
    assert grandchild.body == "child body"
    assert grandchild.label == "renamed label"
    assert grandchild.origin_path == "src/spine/db"
    assert grandchild.updated_at > child.updated_at > child.created_at

    async with sessions() as session:
        revisions = (
            await session.scalars(
                select(MemoryRevision)
                .where(MemoryRevision.memory_id == memory_id)
                .order_by(MemoryRevision.revision)
            )
        ).all()
    assert [revision.rev_uid for revision in revisions] == [root_uid, child_uid, grandchild_uid]
    assert [revision.parent_uid for revision in revisions] == [None, root_uid, child_uid]
    assert [revision.revision for revision in revisions] == [1, 2, 3]
    assert [(revision.body, revision.label) for revision in revisions] == [
        ("root body", "original label"),
        ("child body", "original label"),
        ("child body", "renamed label"),
    ]
    assert (revisions[1].editor, revisions[1].origin_machine_id, revisions[1].reason) == (
        "agent:writer",
        "machine-child",
        "body correction",
    )


async def test_competing_cas_has_one_winner_and_current_409(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = database
    memory_id = uuid4()
    root_uid = _rev_uid(201)
    await _seed_memory(
        sessions,
        memory_id=memory_id,
        root_uid=root_uid,
        principal_id=f"race-{memory_id}",
        label="race label",
    )

    ready = asyncio.Event()
    ready_lock = asyncio.Lock()
    ready_count = 0

    async def contender(body: str, rev_uid: str) -> MemoryUnitSnapshot:
        nonlocal ready_count
        async with sessions.begin() as session:
            async with ready_lock:
                ready_count += 1
                if ready_count == 2:
                    ready.set()
            await ready.wait()
            return await cas_update_memory_unit(
                session,
                CasUpdate(
                    memory_id=memory_id,
                    expected_revision=1,
                    rev_uid=rev_uid,
                    editor="agent:race",
                    origin_machine_id="machine-race",
                    changes=MemoryUnitChanges(body=body),
                ),
            )

    results = await asyncio.gather(
        contender("writer A", _rev_uid(202)),
        contender("writer B", _rev_uid(203)),
        return_exceptions=True,
    )
    winners = [result for result in results if isinstance(result, MemoryUnitSnapshot)]
    conflicts = [result for result in results if isinstance(result, MemoryCasConflictError)]

    assert len(winners) == 1
    assert len(conflicts) == 1
    assert conflicts[0].status_code == 409
    assert conflicts[0].current.revision == 2
    assert conflicts[0].current.body == winners[0].body

    async with sessions() as session:
        head = await session.get(MemoryUnit, memory_id)
        revision_count = await session.scalar(
            select(func.count())
            .select_from(MemoryRevision)
            .where(MemoryRevision.memory_id == memory_id)
        )
    assert head is not None
    assert head.revision == 2
    assert head.body == winners[0].body
    assert revision_count == 2


async def test_revision_append_failure_rolls_back_head_update(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = database
    memory_id = uuid4()
    root_uid = _rev_uid(301)
    await _seed_memory(
        sessions,
        memory_id=memory_id,
        root_uid=root_uid,
        principal_id=f"rollback-{memory_id}",
        label="rollback label",
    )

    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            await cas_update_memory_unit(
                session,
                CasUpdate(
                    memory_id=memory_id,
                    expected_revision=1,
                    rev_uid=root_uid,
                    editor="agent:broken",
                    origin_machine_id="machine-broken",
                    changes=MemoryUnitChanges(body="must roll back"),
                ),
            )

    async with sessions() as session:
        head = await session.get(MemoryUnit, memory_id)
        revisions = (
            await session.scalars(
                select(MemoryRevision).where(MemoryRevision.memory_id == memory_id)
            )
        ).all()
    assert head is not None
    assert (head.revision, head.body) == (1, "root body")
    assert [revision.rev_uid for revision in revisions] == [root_uid]


async def test_lineage_error_rolls_back_when_caught_inside_outer_transaction(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = database
    memory_id = uuid4()
    async with sessions.begin() as session:
        await session.execute(
            insert(MemoryUnit).values(
                id=memory_id,
                principal_id=f"broken-lineage-{memory_id}",
                label="broken lineage",
                body="unchanged body",
                kind="fact",
                embedding=list(ZERO_EMBEDDING),
                embedding_model="s1-test",
            )
        )
        with pytest.raises(MemoryLineageError):
            await cas_update_memory_unit(
                session,
                CasUpdate(
                    memory_id=memory_id,
                    expected_revision=1,
                    rev_uid=_rev_uid(351),
                    editor="agent:broken-lineage",
                    origin_machine_id="machine-broken-lineage",
                    changes=MemoryUnitChanges(body="must roll back"),
                ),
            )

        head_inside_outer_transaction = await session.get(MemoryUnit, memory_id)
        assert head_inside_outer_transaction is not None
        assert (head_inside_outer_transaction.revision, head_inside_outer_transaction.body) == (
            1,
            "unchanged body",
        )

    async with sessions() as session:
        persisted = await session.get(MemoryUnit, memory_id)
        revision_count = await session.scalar(
            select(func.count())
            .select_from(MemoryRevision)
            .where(MemoryRevision.memory_id == memory_id)
        )
    assert persisted is not None
    assert (persisted.revision, persisted.body) == (1, "unchanged body")
    assert revision_count == 0


async def test_cas_requires_a_caller_owned_transaction(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = database
    memory_id = uuid4()
    root_uid = _rev_uid(352)
    await _seed_memory(
        sessions,
        memory_id=memory_id,
        root_uid=root_uid,
        principal_id=f"transaction-{memory_id}",
        label="transaction boundary",
    )
    command = CasUpdate(
        memory_id=memory_id,
        expected_revision=1,
        rev_uid=_rev_uid(353),
        editor="agent:transaction",
        origin_machine_id="machine-transaction",
        changes=MemoryUnitChanges(body="rolled back by caller"),
    )

    async with sessions() as session:
        with pytest.raises(RuntimeError, match="explicit caller transaction"):
            await cas_update_memory_unit(session, command)
        await session.scalar(select(1))
        with pytest.raises(RuntimeError, match="explicit caller transaction"):
            await cas_update_memory_unit(session, command)
        await session.rollback()

    async with sessions() as session:
        transaction = await session.begin()
        changed = await cas_update_memory_unit(session, command)
        assert (changed.revision, changed.body) == (2, "rolled back by caller")
        await transaction.rollback()

    async with sessions() as session:
        persisted = await session.get(MemoryUnit, memory_id)
        revision_count = await session.scalar(
            select(func.count())
            .select_from(MemoryRevision)
            .where(MemoryRevision.memory_id == memory_id)
        )
    assert persisted is not None
    assert (persisted.revision, persisted.body) == (1, "root body")
    assert revision_count == 1


def test_cas_command_requires_a_canonical_ulid() -> None:
    with pytest.raises(ValueError, match="canonical 26-character ULID"):
        CasUpdate(
            memory_id=uuid4(),
            expected_revision=1,
            rev_uid="not-a-ulid",
            editor="agent:invalid",
            origin_machine_id="machine-invalid",
            changes=MemoryUnitChanges(body="not written"),
        )


async def test_tombstone_is_revisioned_and_releases_active_label(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = database
    memory_id = uuid4()
    replacement_id = uuid4()
    root_uid = _rev_uid(401)
    principal_id = f"tombstone-{memory_id}"
    label = "reusable label"
    await _seed_memory(
        sessions,
        memory_id=memory_id,
        root_uid=root_uid,
        principal_id=principal_id,
        label=label,
    )

    async with sessions.begin() as session:
        tombstone = await tombstone_memory_unit(
            session,
            memory_id=memory_id,
            expected_revision=1,
            rev_uid=_rev_uid(402),
            editor="user",
            origin_machine_id="machine-tombstone",
            reason="remove",
        )
    async with sessions.begin() as session:
        await _insert_memory_and_root(
            session,
            memory_id=replacement_id,
            root_uid=_rev_uid(403),
            principal_id=principal_id,
            label=label,
            body="replacement body",
        )

    assert tombstone.status == "tombstoned"
    assert tombstone.revision == 2
    async with sessions() as session:
        original = await session.get(MemoryUnit, memory_id)
        replacement = await session.get(MemoryUnit, replacement_id)
        revisions = (
            await session.scalars(
                select(MemoryRevision)
                .where(MemoryRevision.memory_id == memory_id)
                .order_by(MemoryRevision.revision)
            )
        ).all()
    assert original is not None
    assert (original.status, original.revision) == ("tombstoned", 2)
    assert replacement is not None
    assert replacement.status == "active"
    assert [revision.parent_uid for revision in revisions] == [None, root_uid]
    assert [revision.revision for revision in revisions] == [1, 2]
