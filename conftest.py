"""Test isolation: every test session uses its own database (furnace_test), created
and migrated on demand, so a running dev stack (API + embedded worker on the dev
database) can never claim or mutate test jobs."""

import os
import subprocess
import sys
from pathlib import Path

_DEV = os.environ.get(
    "FURNACE_DATABASE_URL", "postgresql+asyncpg://furnace:furnace@localhost:5433/furnace"
)
_BASE, _, _DBNAME = _DEV.rpartition("/")
TEST_DB = _DBNAME if _DBNAME.endswith("_test") else f"{_DBNAME}_test"
os.environ["FURNACE_DATABASE_URL"] = f"{_BASE}/{TEST_DB}"
os.environ.setdefault("FURNACE_ENV", "dev")
os.environ.setdefault("FURNACE_BLOB_DIR", str(Path(__file__).parent / ".data" / "test-blobs"))


def _ensure_test_db() -> None:
    import asyncio

    import asyncpg

    dsn = _BASE.replace("postgresql+asyncpg", "postgresql") + "/postgres"

    async def create() -> None:
        conn = await asyncpg.connect(dsn)
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB)
            if not exists:
                await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
        finally:
            await conn.close()

    try:
        asyncio.run(create())
    except (OSError, asyncpg.PostgresError):
        return  # no database available: db-marked tests will fail loudly on their own
    ini = Path(__file__).parent / "packages/furnace/src/furnace/db/alembic.ini"
    subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, "-m", "alembic", "-c", str(ini), "upgrade", "head"],
        check=True,
        env=os.environ.copy(),
        capture_output=True,
    )


_ensure_test_db()
