"""Furnace API entrypoint."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import furnace
from fastapi import FastAPI
from furnace.jobs.worker import run_forever
from furnace.settings import get_settings

from furnace_api.routers import bench, github, live, scans, system

log = logging.getLogger("furnace.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    task: asyncio.Task[None] | None = None
    if settings.embedded_worker:
        # Free-tier hosting has no separate worker process: run the cpu queue in-process.
        task = asyncio.create_task(run_forever(f"{settings.worker_id}-embedded", ["cpu"]))
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Furnace API", version=furnace.__version__, lifespan=lifespan)
app.include_router(system.router)
app.include_router(scans.router)
app.include_router(bench.router)
app.include_router(github.router)
app.include_router(live.router)
