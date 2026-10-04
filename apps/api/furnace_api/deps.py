"""FastAPI dependencies."""

from collections.abc import AsyncIterator

from furnace.db.session import get_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession


async def db_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
