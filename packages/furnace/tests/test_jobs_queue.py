import asyncio

import pytest
from furnace.db.models import Job
from furnace.db.session import session_scope
from furnace.jobs import queue
from sqlalchemy import func, select

pytestmark = pytest.mark.db


async def _drain(worker: str, claimed: list[str]) -> None:
    while True:
        async with session_scope() as s:
            job = await queue.claim(s, worker=worker, queues=["cpu"], lease_s=60)
            if job is None:
                return
            claimed.append(str(job.id))
            await queue.complete(s, job.id, {"by": worker})


async def test_concurrent_workers_never_double_claim(clean_jobs):
    async with session_scope() as s:
        for i in range(40):
            await queue.enqueue(s, queue="cpu", kind="system.ping", payload={"i": i})
    claimed: list[str] = []
    await asyncio.gather(*[_drain(f"w{i}", claimed) for i in range(4)])
    assert len(claimed) == 40
    assert len(set(claimed)) == 40
    async with session_scope() as s:
        n = await s.scalar(select(func.count()).where(Job.status == "succeeded"))
    assert n == 40


async def test_queue_routing_and_retry_backoff(clean_jobs):
    async with session_scope() as s:
        await queue.enqueue(s, queue="runner", kind="bench.run", max_attempts=2)
    async with session_scope() as s:
        assert await queue.claim(s, worker="cpu-only", queues=["cpu"], lease_s=60) is None
    async with session_scope() as s:
        job = await queue.claim(s, worker="laptop", queues=["runner"], lease_s=60)
        assert job is not None and job.attempts == 1
        await queue.fail(s, job, "boom")
    async with session_scope() as s:
        j = await s.get(Job, job.id)
        assert j is not None
        assert j.status == "queued" and j.locked_by is None
        # backoff pushes run_after into the future: not immediately claimable
        assert await queue.claim(s, worker="laptop", queues=["runner"], lease_s=60) is None


async def test_abandoned_job_is_reclaimed_after_lease(clean_jobs):
    from sqlalchemy import text

    async with session_scope() as s:
        await queue.enqueue(s, queue="cpu", kind="system.ping")
    async with session_scope() as s:
        job = await queue.claim(s, worker="dead", queues=["cpu"], lease_s=60)
        assert job is not None
    async with session_scope() as s:
        await s.execute(
            text("UPDATE jobs SET heartbeat_at = now() - interval '10 minutes' WHERE id = :i"),
            {"i": job.id},
        )
    async with session_scope() as s:
        again = await queue.claim(s, worker="alive", queues=["cpu"], lease_s=60)
        assert again is not None and again.id == job.id and again.locked_by == "alive"


def test_worker_entrypoint_sees_every_registered_handler():
    """Regression: run as `python -m`, the worker once had a registry with only system.ping."""
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "furnace.jobs.worker", "--list-handlers"],
        capture_output=True, text=True, check=True, timeout=60,
    ).stdout.split()  # fmt: skip
    assert {"guard.local", "guard.pr", "repair.pr", "scan.run", "system.ping"} <= set(out)


async def test_orphaned_and_abandoned_jobs_are_failed_not_left_running(clean_jobs):
    """Regression: a runner restarted mid-run left a guard job 'running' forever (max_attempts=1
    means the lease never re-claims it) and the UI showed it as active."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    async with session_scope() as s:
        mine = await queue.enqueue(s, queue="runner", kind="guard.local", max_attempts=1)
        stale = await queue.enqueue(s, queue="runner", kind="guard.local", max_attempts=1)
        retryable = await queue.enqueue(s, queue="runner", kind="system.ping", max_attempts=3)
        fresh = await queue.enqueue(s, queue="runner", kind="guard.local", max_attempts=1)
    old = datetime.now(UTC) - timedelta(seconds=600)
    async with session_scope() as s:
        for job, worker, hb in (
            (mine, "laptop-runner", old),
            (stale, "other", old),
            (retryable, "other", old),
            (fresh, "other", datetime.now(UTC)),
        ):
            await s.execute(
                update(Job).where(Job.id == job.id).values(
                    status="running", locked_by=worker, heartbeat_at=hb, attempts=1
                )
            )  # fmt: skip
    async with session_scope() as s:
        assert await queue.fail_orphans(s, "laptop-runner") == 1
        assert await queue.reap_abandoned(s, lease_s=120) == 1  # `stale` only
    async with session_scope() as s:
        status = {j.id: (j.status, j.error or "") for j in (await s.execute(select(Job))).scalars()}
    assert status[mine.id][0] == "failed" and "restarted" in status[mine.id][1]
    assert status[stale.id][0] == "failed" and "no heartbeat" in status[stale.id][1]
    assert status[retryable.id][0] == "running"  # left for claim() to re-take
    assert status[fresh.id][0] == "running"


async def test_enqueue_once_keeps_one_active_job_per_key(clean_jobs):
    async with session_scope() as s:
        a, created_a = await queue.enqueue_once(s, queue="runner", kind="guard.pr", dedupe_key="k1")
        b, created_b = await queue.enqueue_once(s, queue="runner", kind="guard.pr", dedupe_key="k1")
        c, created_c = await queue.enqueue_once(s, queue="runner", kind="guard.pr", dedupe_key="k2")
    assert created_a and not created_b and created_c
    assert b.id == a.id and c.id != a.id
    # a finished job leaves the active set: a deliberate re-run with the same key is allowed
    async with session_scope() as s:
        await queue.complete(s, a.id, {})
    async with session_scope() as s:
        d, created_d = await queue.enqueue_once(s, queue="runner", kind="guard.pr", dedupe_key="k1")
    assert created_d and d.id != a.id


async def test_concurrent_enqueue_once_creates_exactly_one(clean_jobs):
    async def one():
        async with session_scope() as s:
            return await queue.enqueue_once(s, queue="runner", kind="guard.pr", dedupe_key="race")

    results = await asyncio.gather(*[one() for _ in range(8)])
    assert sum(created for _, created in results) == 1
    assert len({job.id for job, _ in results}) == 1


@pytest.mark.adversarial
async def test_a_stale_claim_cannot_overwrite_the_claim_that_replaced_it(clean_jobs):
    """Fencing: worker A stalls past its lease, B re-claims; A's late completion, failure
    and heartbeat must all be refused, and B's outcome stands."""
    from sqlalchemy import text

    async with session_scope() as s:
        await queue.enqueue(s, queue="cpu", kind="system.ping", max_attempts=3)
    async with session_scope() as s:
        a = await queue.claim(s, worker="A", queues=["cpu"], lease_s=60)
    assert a is not None and a.attempts == 1
    async with session_scope() as s:
        await s.execute(
            text("UPDATE jobs SET heartbeat_at = now() - interval '10 minutes' WHERE id = :i"),
            {"i": a.id},
        )
    async with session_scope() as s:
        b = await queue.claim(s, worker="B", queues=["cpu"], lease_s=60)
    assert b is not None and b.id == a.id and b.attempts == 2
    async with session_scope() as s:
        assert not await queue.heartbeat(s, a.id, "A", 1)
        assert not await queue.complete(s, a.id, {"by": "A"}, worker="A", attempt=1)
        assert not await queue.fail(s, a, "A gave up", fenced=True)
    async with session_scope() as s:
        assert await queue.heartbeat(s, b.id, "B", 2)
        assert await queue.complete(s, b.id, {"by": "B"}, worker="B", attempt=2)
    async with session_scope() as s:
        j = await s.get(Job, a.id)
        assert j is not None and j.status == "succeeded" and j.result == {"by": "B"}


@pytest.fixture
def short_lease(monkeypatch):
    from furnace.settings import get_settings

    monkeypatch.setenv("FURNACE_JOB_LEASE_SECONDS", "2")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_job_timeout_fails_the_job_with_the_reason(clean_jobs, short_lease):
    from furnace.jobs import worker

    async def hang(ctx):
        await asyncio.sleep(60)

    worker.HANDLERS["test.hang"] = hang
    try:
        async with session_scope() as s:
            job, _ = await queue.enqueue_once(
                s, queue="cpu", kind="test.hang", dedupe_key="t", max_attempts=1, timeout_s=1
            )
        assert await asyncio.wait_for(worker.run_one("w-timeout", ["cpu"]), 20)
        async with session_scope() as s:
            j = await s.get(Job, job.id)
        assert j is not None and j.status == "failed" and "timed out after 1 s" in (j.error or "")
    finally:
        del worker.HANDLERS["test.hang"]


@pytest.mark.adversarial
async def test_lost_lease_cancels_the_running_handler(clean_jobs, short_lease):
    """If another claim takes the job (this worker stalled), the heartbeat notices and the
    handler is cancelled before it can write anything else; the other claim's state stands."""
    from furnace.jobs import worker
    from sqlalchemy import text

    cancelled = asyncio.Event()

    async def long_job(ctx):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    worker.HANDLERS["test.long"] = long_job
    try:
        async with session_scope() as s:
            job = await queue.enqueue(s, queue="cpu", kind="test.long", max_attempts=3)
        run = asyncio.create_task(worker.run_one("w-slow", ["cpu"]))
        await asyncio.sleep(0.5)
        async with session_scope() as s:  # another worker re-claims it
            await s.execute(
                text("UPDATE jobs SET locked_by='thief', attempts=attempts+1 WHERE id=:i"),
                {"i": job.id},
            )
        assert await asyncio.wait_for(run, 15)
        assert cancelled.is_set()
        async with session_scope() as s:
            j = await s.get(Job, job.id)
        assert j is not None and j.status == "running" and j.locked_by == "thief"
    finally:
        del worker.HANDLERS["test.long"]
