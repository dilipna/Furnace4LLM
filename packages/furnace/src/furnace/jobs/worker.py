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
import uuid
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


async def _heartbeat_loop(job_id: uuid.UUID, worker_id: str, every_s: float) -> None:
    while True:
        await asyncio.sleep(every_s)
        async with session_scope() as s:
            await queue.heartbeat(s, job_id, worker_id)


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
    hb = asyncio.create_task(
        _heartbeat_loop(job.id, worker_id, max(5.0, settings.job_lease_seconds / 4))
    )
    try:
        if fn is None:
            raise LookupError(f"no handler registered for job kind {job.kind!r}")
        result = await fn(ctx)
        async with session_scope() as s:
            await queue.complete(s, job.id, result)
        log.info("job %s %s succeeded", job.kind, job.id)
    except Exception as exc:
        log.exception("job %s %s failed", job.kind, job.id)
        async with session_scope() as s:
            await queue.emit(s, job.id, "error", str(exc), level="error")
            await queue.fail(s, job, f"{exc}\n{traceback.format_exc()}")
    finally:
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb
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
