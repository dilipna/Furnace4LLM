"""Postgres-backed job queue.

Claiming uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so any number of workers
(the API's embedded cpu worker, the laptop runner) can poll the same table
without double-claiming. Workers heartbeat; a job whose heartbeat is older
than the lease is considered abandoned and becomes claimable again.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from furnace.db.models import Job, JobEvent

QUEUES = ("cpu", "runner")

_CLAIM_SQL = text(
    """
    UPDATE jobs SET
        status = 'running',
        attempts = attempts + 1,
        locked_by = :worker,
        heartbeat_at = now()
    WHERE id = (
        SELECT id FROM jobs
        WHERE queue = ANY(:queues)
          AND run_after <= now()
          AND (
                status = 'queued'
             OR (status = 'running' AND heartbeat_at < now() - make_interval(secs => :lease))
          )
          AND attempts < max_attempts
        ORDER BY run_after, created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id
    """
)


async def enqueue(
    session: AsyncSession,
    *,
    queue: str,
    kind: str,
    payload: dict[str, Any] | None = None,
    org_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    max_attempts: int = 3,
    delay_s: float = 0.0,
) -> Job:
    if queue not in QUEUES:
        raise ValueError(f"unknown queue {queue!r}")
    job = Job(
        queue=queue,
        kind=kind,
        payload=payload or {},
        org_id=org_id,
        project_id=project_id,
        max_attempts=max_attempts,
        run_after=datetime.now(UTC) + timedelta(seconds=delay_s),
    )
    session.add(job)
    await session.flush()
    return job


async def claim(
    session: AsyncSession, *, worker: str, queues: list[str], lease_s: int
) -> Job | None:
    """Atomically claim one runnable job. Caller must commit to release the row lock."""
    row = (
        await session.execute(_CLAIM_SQL, {"worker": worker, "queues": queues, "lease": lease_s})
    ).first()
    if row is None:
        return None
    return await session.get(Job, row[0], populate_existing=True)


async def heartbeat(session: AsyncSession, job_id: uuid.UUID, worker: str) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.locked_by == worker)
        .values(heartbeat_at=datetime.now(UTC))
    )


async def complete(session: AsyncSession, job_id: uuid.UUID, result: dict[str, Any] | None) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="succeeded", result=result or {}, finished_at=datetime.now(UTC))
    )


async def fail(session: AsyncSession, job: Job, error: str) -> None:
    """Record failure; retry with exponential backoff unless attempts are exhausted."""
    if job.attempts >= job.max_attempts:
        values: dict[str, Any] = {
            "status": "failed",
            "error": error[:4000],
            "finished_at": datetime.now(UTC),
        }
    else:
        backoff = 5 * (2 ** (job.attempts - 1))
        values = {
            "status": "queued",
            "error": error[:4000],
            "locked_by": None,
            "run_after": datetime.now(UTC) + timedelta(seconds=backoff),
        }
    await session.execute(update(Job).where(Job.id == job.id).values(**values))


async def fail_orphans(session: AsyncSession, worker: str) -> int:
    """Jobs still marked running under this worker id belonged to its previous process
    (killed or restarted mid-job): fail them so they do not look active forever."""
    r = await session.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_by == worker)
        .values(
            status="failed",
            error="the worker restarted while this job was running",
            finished_at=datetime.now(UTC),
        )
    )
    return r.rowcount or 0  # type: ignore[attr-defined]


async def reap_abandoned(session: AsyncSession, lease_s: int) -> int:
    """Running jobs whose heartbeat stopped longer than the lease ago and that have no attempt
    left cannot be re-claimed: fail them with the reason (others are re-claimed by claim())."""
    r = await session.execute(
        update(Job)
        .where(
            Job.status == "running",
            Job.heartbeat_at < datetime.now(UTC) - timedelta(seconds=lease_s),
            Job.attempts >= Job.max_attempts,
        )
        .values(
            status="failed",
            error=f"abandoned: no heartbeat for more than {lease_s} s (worker gone)",
            finished_at=datetime.now(UTC),
        )
    )
    return r.rowcount or 0  # type: ignore[attr-defined]


async def emit(
    session: AsyncSession,
    job_id: uuid.UUID,
    stage: str,
    msg: str,
    *,
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    session.add(JobEvent(job_id=job_id, stage=stage, msg=msg, level=level, data=data or {}))
    await session.flush()


async def events_since(
    session: AsyncSession, job_id: uuid.UUID, after_id: int = 0
) -> list[JobEvent]:
    rows = await session.execute(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.id > after_id)
        .order_by(JobEvent.id)
    )
    return list(rows.scalars())
