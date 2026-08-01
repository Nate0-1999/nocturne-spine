"""Programmatic access to Spine's packaged Alembic migrations."""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config

DATABASE_URL_ATTRIBUTE = "spine.database_url"
MIGRATION_RESOURCE = "spine:db/migrations"


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


def main() -> None:
    """Upgrade the database named by ``SPINE_DATABASE_URL``."""

    database_url = os.environ.get("SPINE_DATABASE_URL")
    if not database_url:
        raise SystemExit("SPINE_DATABASE_URL is required")
    upgrade_head(database_url)


if __name__ == "__main__":  # pragma: no cover - exercised by Compose
    main()
