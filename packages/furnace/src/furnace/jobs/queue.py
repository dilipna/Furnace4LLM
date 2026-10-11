"""Postgres-backed job queue.

Claiming uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so any number of workers
(the API's embedded cpu worker, the laptop runner) can poll the same table
without double-claiming. Workers heartbeat; a job whose heartbeat is older
than the lease is considered abandoned and becomes claimable again.

Fencing: a claim is identified by (worker id, attempt number). Heartbeats, completion
and failure only touch the row while that claim still holds it, so a worker that lost
its lease (stalled, partitioned) cannot overwrite the outcome of the attempt that
re-claimed the job; it learns it lost the lease and stops.

Idempotent enqueue: `enqueue_once` takes a dedupe key; a partial unique index allows at
most one *queued or running* job per key, so retried or redelivered triggers attach to
the active job instead of starting a second one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
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


async def enqueue_once(
    session: AsyncSession,
    *,
    queue: str,
    kind: str,
    dedupe_key: str,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 3,
    timeout_s: int | None = None,
) -> tuple[Job, bool]:
    """Enqueue unless a queued/running job with `dedupe_key` exists. Returns (job, created);
    when not created, `job` is the active job the trigger attached to."""
    if queue not in QUEUES:
        raise ValueError(f"unknown queue {queue!r}")
    stmt = (
        insert(Job)
        .values(
            queue=queue,
            kind=kind,
            payload=payload or {},
            max_attempts=max_attempts,
            dedupe_key=dedupe_key,
            timeout_s=timeout_s,
            status="queued",
            attempts=0,
        )
        .on_conflict_do_nothing(
            index_elements=[Job.dedupe_key],
            index_where=text("dedupe_key IS NOT NULL AND status IN ('queued', 'running')"),
        )
        .returning(Job.id)
    )
    new_id = (await session.execute(stmt)).scalar_one_or_none()
    if new_id is not None:
        job = await session.get(Job, new_id)
        assert job is not None
        return job, True
    existing = (
        await session.execute(
            select(Job).where(Job.dedupe_key == dedupe_key, Job.status.in_(("queued", "running")))
        )
    ).scalar_one_or_none()
    if existing is None:  # the active job finished between the insert and this read: retry
        return await enqueue_once(
            session,
            queue=queue,
            kind=kind,
            dedupe_key=dedupe_key,
            payload=payload,
            max_attempts=max_attempts,
            timeout_s=timeout_s,
        )
    return existing, False


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


def _held_by(job_id: uuid.UUID, worker: str | None, attempt: int | None) -> list[Any]:
    """Row predicate: the job, and (when fencing) still running under this exact claim."""
    conds: list[Any] = [Job.id == job_id]
    if worker is not None:
        conds += [Job.status == "running", Job.locked_by == worker]
    if attempt is not None:
        conds.append(Job.attempts == attempt)
    return conds


async def heartbeat(
    session: AsyncSession, job_id: uuid.UUID, worker: str, attempt: int | None = None
) -> bool:
    """Extend the lease. False means this claim no longer holds the job (lease lost)."""
    r = await session.execute(
        update(Job).where(*_held_by(job_id, worker, attempt)).values(heartbeat_at=datetime.now(UTC))
    )
    return bool(r.rowcount)  # type: ignore[attr-defined]


async def complete(
    session: AsyncSession,
    job_id: uuid.UUID,
    result: dict[str, Any] | None,
    *,
    worker: str | None = None,
    attempt: int | None = None,
) -> bool:
    """Mark succeeded. With `worker`/`attempt`, only if that claim still holds the job;
    returns False when the write was fenced off (the result is then discarded)."""
    r = await session.execute(
        update(Job)
        .where(*_held_by(job_id, worker, attempt))
        .values(status="succeeded", result=result or {}, finished_at=datetime.now(UTC))
    )
    return bool(r.rowcount)  # type: ignore[attr-defined]


async def fail(session: AsyncSession, job: Job, error: str, *, fenced: bool = False) -> bool:
    """Record failure; retry with exponential backoff unless attempts are exhausted.
    `fenced`: only if this claim (job.locked_by, job.attempts) still holds the job."""
    where = _held_by(job.id, job.locked_by, job.attempts) if fenced else [Job.id == job.id]
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
    r = await session.execute(update(Job).where(*where).values(**values))
    return bool(r.rowcount)  # type: ignore[attr-defined]


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
