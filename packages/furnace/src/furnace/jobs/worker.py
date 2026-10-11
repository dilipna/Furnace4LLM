"""Worker loop. The same binary runs as the API-embedded `cpu` worker and as the
laptop `runner` (GPU, Docker sandbox, Playwright)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import platform
import shutil
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from furnace_bench.telemetry.nvml import NVMLSampler
from sqlalchemy.dialects.postgresql import insert

from furnace.db.models import Job, Runner
from furnace.db.session import session_scope
from furnace.jobs import queue
from furnace.settings import get_settings

log = logging.getLogger("furnace.worker")


class JobContext:
    """Passed to handlers: lets them emit progress events in their own transactions,
    so the UI sees progress while the job is still running."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self.lease_lost = False  # set by the heartbeat when another claim took the job

    @property
    def payload(self) -> dict[str, Any]:
        return self.job.payload

    async def emit(self, stage: str, msg: str, *, level: str = "info", **data: Any) -> None:
        async with session_scope() as s:
            await queue.emit(s, self.job.id, stage, msg, level=level, data=data)


Handler = Callable[[JobContext], Awaitable[dict[str, Any] | None]]
HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return register


@handler("system.ping")
async def _ping(ctx: JobContext) -> dict[str, Any]:
    await ctx.emit("ping", "pong")
    return {"pong": True, "node": platform.node()}


def detect_capabilities() -> dict[str, Any]:
    nvml = NVMLSampler()
    return {
        "platform": platform.platform(),
        "docker": bool(shutil.which("docker")),
        "gpu": nvml.name if nvml.available else None,
        "gpu_driver": nvml.driver if nvml.available else None,
    }


async def _register(worker_id: str, queues: list[str]) -> None:
    caps = detect_capabilities()
    async with session_scope() as s:
        stmt = insert(Runner).values(id=worker_id, queues=queues, capabilities=caps)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Runner.id],
            set_={"queues": queues, "capabilities": caps, "last_seen": datetime.now(UTC)},
        )
        await s.execute(stmt)


async def _heartbeat_loop(
    ctx: JobContext, worker_id: str, every_s: float, lease_s: float, work: asyncio.Task[Any]
) -> None:
    """Extend the lease every `every_s`. If the claim no longer holds the job, or the
    database has been unreachable for longer than the lease (so another worker may have
    re-claimed it), cancel the handler: two runs must not both write to GitHub."""
    loop = asyncio.get_running_loop()
    last_ok = loop.time()
    while True:
        await asyncio.sleep(every_s)
        try:
            async with session_scope() as s:
                held = await queue.heartbeat(s, ctx.job.id, worker_id, ctx.job.attempts)
        except Exception:
            log.warning("heartbeat for job %s failed", ctx.job.id, exc_info=True)
            if loop.time() - last_ok < lease_s:
                continue
            held = False
        if not held:
            log.error("job %s: lease lost; cancelling this run", ctx.job.id)
            ctx.lease_lost = True
            work.cancel()
            return
        last_ok = loop.time()


async def run_one(worker_id: str, queues: list[str]) -> bool:
    """Claim and execute at most one job. Returns True if a job was processed."""
    settings = get_settings()
    async with session_scope() as s:
        job = await queue.claim(
            s, worker=worker_id, queues=queues, lease_s=settings.job_lease_seconds
        )
    if job is None:
        return False

    ctx = JobContext(job)
    fn = HANDLERS.get(job.kind)
    timeout = job.timeout_s or settings.job_timeout_seconds

    async def execute() -> dict[str, Any] | None:
        if fn is None:
            raise LookupError(f"no handler registered for job kind {job.kind!r}")
        return await fn(ctx)

    work = asyncio.create_task(execute())
    hb = asyncio.create_task(
        _heartbeat_loop(
            ctx,
            worker_id,
            max(1.0, settings.job_lease_seconds / 4),
            settings.job_lease_seconds,
            work,
        )
    )
    error: str | None = None
    try:
        result = await asyncio.wait_for(work, timeout)
        async with session_scope() as s:
            held = await queue.complete(s, job.id, result, worker=worker_id, attempt=job.attempts)
        if held:
            log.info("job %s %s succeeded", job.kind, job.id)
        else:
            log.error(
                "job %s %s finished after losing its lease; result discarded", job.kind, job.id
            )
    except TimeoutError:
        error = f"timed out after {timeout} s (job timeout); handler cancelled"
    except asyncio.CancelledError:
        if not ctx.lease_lost:
            raise  # the worker itself is shutting down
        log.error("job %s %s cancelled: lease lost to another claim", job.kind, job.id)
    except Exception as exc:
        log.exception("job %s %s failed", job.kind, job.id)
        error = f"{exc}\n{traceback.format_exc()}"
    finally:
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb
    if error is not None:
        async with session_scope() as s:
            await queue.emit(s, job.id, "error", error.splitlines()[0], level="error")
            if not await queue.fail(s, job, error, fenced=True):
                log.error("job %s: failure not recorded, lease already lost", job.id)
    return True


async def run_forever(worker_id: str, queues: list[str], idle_sleep_s: float = 1.0) -> None:
    import furnace.jobs.handlers  # noqa: F401  (registers job handlers)

    await _register(worker_id, queues)
    lease = get_settings().job_lease_seconds
    async with session_scope() as s:
        if n := await queue.fail_orphans(s, worker_id):
            log.warning("failed %d job(s) orphaned by this worker's previous process", n)
    log.info("worker %s polling queues %s", worker_id, queues)
    last_seen = asyncio.get_running_loop().time()
    while True:
        processed = await run_one(worker_id, queues)
        now = asyncio.get_running_loop().time()
        if now - last_seen > 30:
            await _register(worker_id, queues)
            async with session_scope() as s:
                if n := await queue.reap_abandoned(s, lease):
                    log.warning("failed %d abandoned job(s) (no heartbeat)", n)
            last_seen = now
        if not processed:
            await asyncio.sleep(idle_sleep_s)


def main() -> None:
    parser = argparse.ArgumentParser(description="Furnace worker / runner")
    parser.add_argument("--queues", default="cpu", help="comma-separated: cpu,runner")
    parser.add_argument("--id", default=None, help="worker id (default: <host>-<queues>)")
    parser.add_argument("--list-handlers", action="store_true", help="print job kinds and exit")
    args = parser.parse_args()
    if args.list_handlers:
        import furnace.jobs.handlers  # noqa: F401

        print(" ".join(sorted(HANDLERS)))
        return
    queues = [q.strip() for q in args.queues.split(",") if q.strip()]
    worker_id = args.id or f"{platform.node()}-{'-'.join(queues)}"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_forever(worker_id, queues))


if __name__ == "__main__":
    # `python -m furnace.jobs.worker` runs this file as __main__, a second copy of the module.
    # Handler modules register into furnace.jobs.worker.HANDLERS, so run that copy's main;
    # running this one would see an empty registry and fail every job but system.ping.
    from furnace.jobs import worker as _canonical

    _canonical.main()
