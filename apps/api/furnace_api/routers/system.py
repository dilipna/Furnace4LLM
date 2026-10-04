"""Health, runner status, and queue smoke-test endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import furnace
from fastapi import APIRouter, Depends
from furnace.db.models import Runner
from furnace.jobs import queue
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


@router.get("/api/runners", response_model=list[RunnerOut])
async def runners(db: DB) -> list[RunnerOut]:
    cutoff = datetime.now(UTC) - timedelta(seconds=90)
    rows = (await db.execute(select(Runner).order_by(Runner.last_seen.desc()))).scalars()
    return [
        RunnerOut(
            id=r.id,
            queues=list(r.queues),
            capabilities=r.capabilities,
            last_seen=r.last_seen,
            online=r.last_seen >= cutoff,
        )
        for r in rows
    ]


class JobRef(BaseModel):
    job_id: str


@router.post("/api/system/ping", response_model=JobRef)
async def ping(db: DB, target: str = "cpu") -> JobRef:
    job = await queue.enqueue(db, queue=target, kind="system.ping")
    return JobRef(job_id=str(job.id))
