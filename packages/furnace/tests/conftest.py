import os

import pytest

DB_URL = os.environ.get(
    "FURNACE_DATABASE_URL", "postgresql+asyncpg://furnace:furnace@localhost:5433/furnace"
)


@pytest.fixture(scope="session")
def db_url() -> str:
    return DB_URL


@pytest.fixture
async def clean_jobs(db_url):
    from furnace.db.session import session_scope
    from sqlalchemy import text

    async with session_scope(db_url) as s:
        await s.execute(text("TRUNCATE jobs CASCADE"))
    yield
