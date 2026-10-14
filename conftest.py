"""Test isolation.

* Every test session uses its own database (furnace_test), created and migrated on demand,
  so a running dev stack (API + embedded worker on the dev database) can never claim or
  mutate test jobs.
* Settings come only from the process environment and what each test sets: the developer's
  .env (GitHub App id, key path, webhook secret, allowed repositories, Guard settings) is
  not read, and FURNACE_GITHUB_* / FURNACE_GUARD_* variables exported in the shell are
  dropped, so a test sees the same configuration on a laptop with a real App as in CI.
* No test can reach real GitHub or smee.io: the real httpx transports refuse those hosts
  (tests use httpx.MockTransport or ASGI transports, which are unaffected).
"""

import os
import subprocess
import sys
from pathlib import Path

import httpx

for _k in [k for k in os.environ if k.startswith(("FURNACE_GITHUB_", "FURNACE_GUARD_"))]:
    del os.environ[_k]

from furnace.settings import Settings, get_settings  # noqa: E402

Settings.model_config["env_file"] = None  # never the developer's .env
get_settings.cache_clear()

_BLOCKED_HOSTS = ("github.com", "githubusercontent.com", "smee.io")


def _refuse_real_github(host: str) -> None:
    if any(host == h or host.endswith("." + h) for h in _BLOCKED_HOSTS):
        raise RuntimeError(f"tests must not contact {host}: use httpx.MockTransport")


_real_send = httpx.HTTPTransport.handle_request
_real_send_async = httpx.AsyncHTTPTransport.handle_async_request


def _guarded_send(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
    _refuse_real_github(request.url.host)
    return _real_send(self, request)


async def _guarded_send_async(
    self: httpx.AsyncHTTPTransport, request: httpx.Request
) -> httpx.Response:
    _refuse_real_github(request.url.host)
    return await _real_send_async(self, request)


httpx.HTTPTransport.handle_request = _guarded_send  # type: ignore[method-assign]
httpx.AsyncHTTPTransport.handle_async_request = _guarded_send_async  # type: ignore[method-assign]

_DEV = os.environ.get(
    "FURNACE_DATABASE_URL", "postgresql+asyncpg://furnace:furnace@localhost:5433/furnace"
)
_BASE, _, _DBNAME = _DEV.rpartition("/")
TEST_DB = _DBNAME if _DBNAME.endswith("_test") else f"{_DBNAME}_test"
os.environ["FURNACE_DATABASE_URL"] = f"{_BASE}/{TEST_DB}"
os.environ.setdefault("FURNACE_ENV", "dev")
# no background lab poller in tests; tests of the live views turn it on explicitly
os.environ.setdefault("FURNACE_LIVE_LAB", "false")
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
