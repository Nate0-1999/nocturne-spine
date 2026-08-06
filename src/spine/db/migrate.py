"""Programmatic access to Spine's packaged Alembic migrations."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection

DATABASE_URL_ATTRIBUTE = "spine.database_url"
MIGRATION_RESOURCE = "spine:db/migrations"
MIGRATION_ADVISORY_LOCK_ID = 5642809481902573646


@contextmanager
def migration_lock(connection: Connection) -> Iterator[None]:
    """Serialize every online migration on one database-owned session lock."""

    parameters = {"lock_id": MIGRATION_ADVISORY_LOCK_ID}
    connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), parameters)
    connection.commit()
    try:
        yield
    finally:
        connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), parameters)
        connection.commit()


def make_alembic_config(database_url: str) -> Config:
    """Build an Alembic config that resolves migrations from the installed package."""

    if not database_url:
        raise ValueError("database_url must not be empty")

    config = Config()
    config.set_main_option("script_location", MIGRATION_RESOURCE)
    config.attributes[DATABASE_URL_ATTRIBUTE] = database_url
    return config


def upgrade_head(database_url: str) -> None:
    """Upgrade one database to the single packaged migration head."""

    command.upgrade(make_alembic_config(database_url), "head")


def packaged_head() -> str:
    """Return the single schema revision expected by this installed Spine build."""

    heads = ScriptDirectory.from_config(
        make_alembic_config("postgresql+asyncpg://unused:unused@127.0.0.1/unused")
    ).get_heads()
    if len(heads) != 1:
        raise RuntimeError("packaged Spine migrations must have one head")
    return heads[0]


def main() -> None:
    """Upgrade the database named by ``SPINE_DATABASE_URL``."""

    database_url = os.environ.get("SPINE_DATABASE_URL")
    if not database_url:
        raise SystemExit("SPINE_DATABASE_URL is required")
    upgrade_head(database_url)


if __name__ == "__main__":  # pragma: no cover - exercised by Compose
    main()
