"""Async engine/session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from furnace.settings import get_settings


@lru_cache
def get_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(url or get_settings().database_url, pool_pre_ping=True)


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
