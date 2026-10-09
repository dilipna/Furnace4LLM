"""Live Guard runs: start a local Guard run on an F1 PR scenario, and stream any Guard
job's structured events (impact, then each check, then the verdict) from job_events."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from furnace.db.models import Job, JobEvent, Runner
from furnace.db.session import session_scope
from furnace.jobs import queue
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from furnace_api.deps import db_session
from furnace_api.routers.bench import RQ_FILES, bench_dir
from furnace_api.sse import sse

router = APIRouter(prefix="/api/guard")
DB = Annotated[AsyncSession, Depends(db_session)]
GUARD_KINDS = ("guard.local", "guard.pr")
ACTIVE_WINDOW = timedelta(minutes=20)  # a queued/running job older than this is stale
RUNNER_ONLINE = timedelta(seconds=90)
PER_IP_LIMIT, PER_IP_WINDOW_S = 3, 600
_RATE: dict[str, deque[float]] = defaultdict(deque)


class GuardRunIn(BaseModel):
    scenario: str = Field(pattern=r"^[a-z0-9_]{1,64}$")


def _known_scenario(name: str) -> bool:
    """Scenarios with RQ3 results: the same set /guard lists."""
    root = bench_dir() / "results"
    rq3 = RQ_FILES["rq3"]
    for d in sorted(root.iterdir() if root.is_dir() else [], reverse=True):
        if (d / rq3).is_file():
            return (d / "rq3" / f"{name}.json").is_file()
    return False


def _job_out(j: Job) -> dict[str, Any]:
    return {
        "job_id": str(j.id),
        "kind": j.kind,
        "status": j.status,
        "payload": j.payload,
        "error": j.error,
        "created_at": j.created_at.isoformat(),
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


async def _active(db: AsyncSession) -> Job | None:
    rows = await db.execute(
        select(Job)
        .where(
            Job.kind.in_(GUARD_KINDS),
            Job.status.in_(("queued", "running")),
            Job.created_at > datetime.now(UTC) - ACTIVE_WINDOW,
        )
        .order_by(Job.created_at.desc())
    )
    return rows.scalars().first()


@router.post("/runs", status_code=201)
async def start_run(body: GuardRunIn, request: Request, db: DB) -> dict[str, Any]:
    if not _known_scenario(body.scenario):
        raise HTTPException(404, "unknown scenario")
    active = await _active(db)
    if active is not None:
        raise HTTPException(409, {"msg": "A Guard run is in progress.", "job_id": str(active.id)})
    cutoff = datetime.now(UTC) - RUNNER_ONLINE
    runners = (await db.execute(select(Runner).where(Runner.last_seen >= cutoff))).scalars()
    if not any("runner" in r.queues for r in runners):
        raise HTTPException(503, "No Guard runner is online (start one with `uv run poe runner`).")
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _RATE[ip]
    while hits and now - hits[0] > PER_IP_WINDOW_S:
        hits.popleft()
    if len(hits) >= PER_IP_LIMIT:
        raise HTTPException(
            429, f"At most {PER_IP_LIMIT} runs per {PER_IP_WINDOW_S // 60} minutes."
        )
    hits.append(now)
    job = await queue.enqueue(
        db, queue="runner", kind="guard.local", payload={"scenario": body.scenario}, max_attempts=1
    )
    return {"job_id": str(job.id)}


@router.get("/runs/latest")
async def latest_run(db: DB, scenario: str | None = None) -> dict[str, Any]:
    q = select(Job).where(Job.kind.in_(GUARD_KINDS))
    if scenario is not None:
        q = q.where(Job.kind == "guard.local", Job.payload["scenario"].astext == scenario)
    job = (await db.execute(q.order_by(Job.created_at.desc()))).scalars().first()
    return _job_out(job) if job else {"job_id": None}


@router.get("/runs/{job_id}/events")
async def run_events(job_id: str, request: Request, db: DB) -> Any:
    try:
        jid = uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(404, "unknown run") from exc
    job = await db.get(Job, jid)
    if job is None or job.kind not in GUARD_KINDS:
        raise HTTPException(404, "unknown run")
    last = 0
    try:
        last = int(request.headers.get("last-event-id", "0"))
    except ValueError:
        last = 0

    async def stream() -> AsyncIterator[dict[str, str]]:
        nonlocal last
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            async with session_scope() as s:
                events: list[JobEvent] = await queue.events_since(s, jid, last)
                current = await s.get(Job, jid)
            for e in events:
                last = e.id
                yield {
                    "event": "progress",
                    "id": str(e.id),
                    "data": json.dumps(
                        {
                            "stage": e.stage,
                            "level": e.level,
                            "msg": e.msg,
                            "ts": e.ts.isoformat(),
                            "data": e.data,
                        }
                    ),
                }
            if current is not None and current.status in ("succeeded", "failed"):
                yield {"event": "status", "data": json.dumps(_job_out(current))}
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.4)

    return sse(stream())
