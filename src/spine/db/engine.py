"""Async SQLAlchemy engine construction."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def make_engine(database_url: str) -> AsyncEngine:
    """Construct an async engine without opening a connection."""

    return create_async_engine(database_url, pool_pre_ping=True)
