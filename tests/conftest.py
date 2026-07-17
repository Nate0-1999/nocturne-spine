"""Shared P0 test fixtures."""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from testcontainers.postgres import PostgresContainer

from spine.config import Settings
from spine.main import create_app

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "p0-test-token"


def _asyncpg_url(url: str) -> str:
    scheme, separator, rest = url.partition("://")
    if not separator:
        raise ValueError("testcontainers returned a malformed Postgres URL")
    if not scheme.startswith("postgres"):
        raise ValueError("testcontainers returned a non-Postgres URL")
    return f"postgresql+asyncpg://{rest}"


@pytest.fixture(scope="session")
def migrated_database_url() -> Iterator[str]:
    """Start pgvector Postgres and apply the production Alembic migration."""

    with PostgresContainer(
        "pgvector/pgvector:pg16",
        username="spine",
        password="spine",
        dbname="spine",
    ) as postgres:
        database_url = _asyncpg_url(postgres.get_connection_url())
        environment = {
            **os.environ,
            "SPINE_DATABASE_URL": database_url,
            "SPINE_TOKEN": TOKEN,
        }
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        yield database_url


@pytest.fixture
def app() -> FastAPI:
    settings = Settings(
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
        token=TOKEN,
    )
    return create_app(settings)
