"""Shared PostgreSQL session advisory-lock lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker


class AdvisoryLockError(RuntimeError):
    """A session advisory lock could not be acquired or released safely."""


@asynccontextmanager
async def session_advisory_lock(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    key: int,
    name: str,
) -> AsyncIterator[AsyncConnection]:
    """Yield one pinned connection only after its session lock is held outside a snapshot."""

    bind = session_factory.kw.get("bind")
    if not isinstance(bind, AsyncEngine):
        raise AdvisoryLockError(f"{name} session factory must be bound to an async engine")
    async with bind.connect() as connection:
        acquired = False
        try:
            await connection.execute(
                text("SELECT pg_advisory_lock(:key)"),
                {"key": key},
            )
            acquired = True
            await connection.commit()
            yield connection
        finally:
            await _release_session_lock(
                connection,
                key=key,
                name=name,
                acquired=acquired,
            )


async def _release_session_lock(
    connection: AsyncConnection,
    *,
    key: int,
    name: str,
    acquired: bool,
) -> None:
    async def cleanup() -> None:
        try:
            if connection.invalidated or connection.closed:
                return
            if connection.in_transaction():
                await connection.rollback()
            released = await connection.scalar(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": key},
            )
            await connection.commit()
            if acquired and released is not True:
                raise AdvisoryLockError(f"{name} advisory lock was not held during cleanup")
        except BaseException as error:
            if not connection.closed:
                await connection.invalidate(error)
            raise

    cleanup_task = asyncio.create_task(cleanup(), name=f"{name}-unlock")
    try:
        await asyncio.shield(cleanup_task)
    except asyncio.CancelledError:
        await cleanup_task
        raise


__all__ = ["AdvisoryLockError", "session_advisory_lock"]
