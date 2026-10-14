"""Health, runner status, and queue smoke-test endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import furnace
from fastapi import APIRouter, Depends
from furnace.db.models import Runner
from furnace.jobs import queue
from furnace.settings import get_settings
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from furnace_api.deps import db_session

router = APIRouter()
DB = Annotated[AsyncSession, Depends(db_session)]


class Health(BaseModel):
    ok: bool
    version: str
    db: bool


class RunnerOut(BaseModel):
    id: str
    queues: list[str]
    capabilities: dict[str, Any]
    last_seen: datetime
    online: bool


@router.get("/healthz", response_model=Health)
async def healthz(db: DB) -> Health:
    db_ok = (await db.execute(text("SELECT 1"))).scalar() == 1
    return Health(ok=db_ok, version=furnace.__version__, db=db_ok)


# Shown to anonymous visitors of a hosted deploy: enough to say what a runner can do, not the
# machine's hostname, OS build or driver version.
PUBLIC_CAPABILITIES = ("gpu", "docker")


@router.get("/api/runners", response_model=list[RunnerOut])
async def runners(db: DB) -> list[RunnerOut]:
    cutoff = datetime.now(UTC) - timedelta(seconds=90)
    rows = (await db.execute(select(Runner).order_by(Runner.last_seen.desc()))).scalars()
    public = get_settings().env == "prod"
    return [
        RunnerOut(
            id=f"runner-{i + 1}" if public else r.id,
            queues=list(r.queues),
            capabilities={k: v for k, v in r.capabilities.items() if k in PUBLIC_CAPABILITIES}
            if public
            else r.capabilities,
            last_seen=r.last_seen,
            online=r.last_seen >= cutoff,
        )
        for i, r in enumerate(rows)
    ]


class JobRef(BaseModel):
    job_id: str


@router.post("/api/system/ping", response_model=JobRef)
async def ping(db: DB, target: str = "cpu") -> JobRef:
    job = await queue.enqueue(db, queue=target, kind="system.ping")
    return JobRef(job_id=str(job.id))
