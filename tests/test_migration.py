"""Integration proof for the authoritative C.2 migration and C.3 seed."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine


async def test_c2_migration_and_v0_seed(migrated_database_url: str) -> None:
    engine = create_async_engine(migrated_database_url)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        )
                    )
                ).scalars()
            )
            extension = await connection.scalar(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            scorer = (
                (
                    await connection.execute(
                        text(
                            "SELECT version, weights, params, active "
                            "FROM scorer_config WHERE version = 'v0'"
                        )
                    )
                )
                .mappings()
                .one()
            )
            embedding_type = await connection.scalar(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) "
                    "FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid = a.attrelid "
                    "WHERE c.relname = 'memory_unit' AND a.attname = 'embedding'"
                )
            )
            origin_path = (
                (
                    await connection.execute(
                        text(
                            "SELECT data_type, is_nullable, column_default "
                            "FROM information_schema.columns "
                            "WHERE table_schema = 'public' "
                            "AND table_name = 'memory_unit' AND column_name = 'origin_path'"
                        )
                    )
                )
                .mappings()
                .one()
            )
            active_label_index = await connection.scalar(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND indexname = 'memory_unit_active_label'"
                )
            )

        assert revision == "0002"
        expected_tables = {
            "memory_unit",
            "memory_revision",
            "thread",
            "injection_event",
            "scorer_config",
        }
        assert expected_tables <= tables
        assert extension == "vector"
        assert embedding_type == "vector(1536)"
        assert origin_path == {
            "data_type": "text",
            "is_nullable": "YES",
            "column_default": None,
        }
        assert active_label_index is not None
        assert "UNIQUE INDEX memory_unit_active_label" in active_label_index
        assert "(principal_id, label)" in active_label_index
        assert "WHERE (status = 'active'::text)" in active_label_index
        assert scorer["version"] == "v0"
        assert scorer["active"] is True
        assert scorer["weights"] == {
            "sem": 0.42,
            "kw": 0.16,
            "time": 0.11,
            "proj": 0.16,
            "freq": 0.08,
            "hist": 0.07,
        }
        assert scorer["params"] == {
            "tau": 0.55,
            "top_k": 8,
            "near_miss_k": 3,
            "budget_tokens": 3000,
            "budget_pct": 0.05,
            "half_life_time_days": 14,
            "half_life_hist_days": 7,
            "never_bias_step": -0.15,
            "quarantine_kills": 3,
            "candidate_pool": 50,
        }
    finally:
        await engine.dispose()


async def test_active_label_is_unique_while_unit_is_active(
    migrated_database_url: str,
) -> None:
    engine = create_async_engine(migrated_database_url)
    embedding = f"[{','.join(['0'] * 1536)}]"
    insert = text(
        """
        INSERT INTO memory_unit (
          principal_id, label, body, kind, embedding, embedding_model
        ) VALUES (
          :principal_id, :label, :body, 'fact', CAST(:embedding AS vector), 'test'
        )
        RETURNING id
        """
    )
    values = {
        "principal_id": "owner",
        "label": "stable-handle",
        "body": "first",
        "embedding": embedding,
    }

    try:
        async with engine.begin() as connection:
            first_id = await connection.scalar(insert, values)

            savepoint = await connection.begin_nested()
            with pytest.raises(IntegrityError):
                await connection.execute(insert, values | {"body": "collision"})
            await savepoint.rollback()

            active_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM memory_unit "
                    "WHERE principal_id = :principal_id AND label = :label "
                    "AND status = 'active'"
                ),
                values,
            )

        assert first_id is not None
        assert active_count == 1
    finally:
        await engine.dispose()
