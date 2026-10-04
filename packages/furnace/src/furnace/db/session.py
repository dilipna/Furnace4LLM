"""Async engine/session factory."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from furnace.settings import get_settings

# asyncpg connections belong to the event loop that created them, so engines are
# cached per (url, loop). Production has one loop per process; tests and the
# TestClient each get their own.
_ENGINES: dict[tuple[str, int], AsyncEngine] = {}


def get_engine(url: str | None = None) -> AsyncEngine:
    url = url or get_settings().database_url
    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = 0
    key = (url, loop_id)
    engine = _ENGINES.get(key)
    if engine is None:
        engine = _ENGINES[key] = create_async_engine(url, pool_pre_ping=True)
    return engine


def get_sessionmaker(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(url), expire_on_commit=False)


@asynccontextmanager
async def session_scope(url: str | None = None) -> AsyncIterator[AsyncSession]:
    """Transactional scope: commits on success, rolls back on error."""
    async with get_sessionmaker(url)() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
