"""Async SQLAlchemy session construction."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Bind sessions to the supplied engine."""

    return async_sessionmaker(engine, expire_on_commit=False)
