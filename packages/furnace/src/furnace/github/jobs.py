"""Runner job: Guard a pull request when the GitHub webhook says it changed.

Enqueued by the API's webhook endpoint on the `runner` queue; executed by the laptop
runner (`uv run poe runner`), which has Docker, the lab endpoint and the App key.
"""

from __future__ import annotations

import asyncio
from typing import Any

from furnace.jobs.worker import JobContext, handler
from furnace.settings import get_settings


def _thread_emitter(ctx: JobContext, stage: str) -> Any:
    """Job events from a worker thread: each is committed before the thread continues,
    so the live view sees a check start before it finishes."""
    loop = asyncio.get_running_loop()

    def emit(ev: dict[str, Any]) -> None:
        msg = ev.get("msg") or _summary(ev)
        data = {k: v for k, v in ev.items() if k not in ("msg", "level", "stage")}
        level = "error" if ev.get("verdict") == "error" else "info"
        fut = asyncio.run_coroutine_threadsafe(ctx.emit(stage, msg, level=level, **data), loop)
        fut.result(timeout=30)

    return emit


def _summary(ev: dict[str, Any]) -> str:
    t = ev.get("type")
    if t == "impact":
        return (
            f"impact: {len(ev['touched'])} nodes touched, {len(ev['selected'])}/"
            f"{ev['full_suite_size']} checks selected ({', '.join(ev['categories']) or 'none'})"
        )
    if t == "check_start":
        return f"{ev['key']}: running"
    if t == "check_done":
        return f"{ev['key']}: {ev['verdict']} ({ev['seconds']}s) {ev['detail'][:200]}"
    if t == "verdict":
        return f"{ev['conclusion']}: {ev['title']}"
    return str(t)


@handler("guard.pr")
async def guard_pull_request(ctx: JobContext) -> dict[str, Any]:
    from furnace import cli
    from furnace.github import flows

    s = get_settings()
    app, suite, questions = _runner_config()
    repo, number = ctx.payload["repo"], int(ctx.payload["number"])
    head_sha = ctx.payload.get("head_sha")
    await ctx.emit("guard", f"Guarding {repo}#{number} at {str(head_sha)[:7]}")
    out = await flows.guard_pr(
        app,
        repo,
        number,
        suite=suite,
        target=cli._target(no_endpoint=False),
        questions=questions,
        max_prompt_tokens=s.guard_max_prompt_tokens,
        on_event=_thread_emitter(ctx, "guard"),
        expected_head_sha=head_sha,
        expected_installation=ctx.payload.get("installation_id"),
    )
    await ctx.emit("guard", f"{out['conclusion']}: {out['title']}")
    result: dict[str, Any] = {
        "check_id": out["check_id"],
        "conclusion": out["conclusion"],
        "title": out["title"],
        "signatures": out.get("signatures", []),
    }
    if out.get("reused"):
        result["reused"] = True
    if out["conclusion"] == "failure" and out.get("signatures") and head_sha:
        result["repair"] = await _maybe_enqueue_repair(ctx, repo, number, head_sha)
    return result


def _runner_config() -> tuple[Any, list[Any], list[str]]:
    """App, suite and questions for webhook jobs. The CLI helpers exit the process on bad
    configuration (SystemExit); inside the runner that would kill the worker instead of
    failing this one job, so convert it."""
    from furnace import cli

    s = get_settings()
    if not s.guard_suite_path:
        raise RuntimeError("FURNACE_GUARD_SUITE_PATH is not set on this runner")
    try:
        return (
            cli._app(),
            cli._suite(str(s.guard_suite_path)),
            cli._questions(str(s.guard_questions_path) if s.guard_questions_path else None),
        )
    except SystemExit as exc:
        raise RuntimeError(f"runner configuration: {exc}") from None


async def _maybe_enqueue_repair(
    ctx: JobContext, repo: str, number: int, head_sha: str
) -> dict[str, Any]:
    """Guard failed with a regression signature the repair loop supports. Enqueue repair
    only with explicit consent (FURNACE_GUARD_AUTO_REPAIR); at most one per PR head."""
    from furnace.db.session import session_scope
    from furnace.github.events import repair_dedupe_key
    from furnace.jobs import queue

    if not get_settings().guard_auto_repair:
        await ctx.emit("repair", "supported regression found; auto-repair is off (run gh-repair)")
        return {"enqueued": False, "reason": "FURNACE_GUARD_AUTO_REPAIR is off"}
    async with session_scope() as s:
        job, created = await queue.enqueue_once(
            s,
            queue="runner",
            kind="repair.pr",
            dedupe_key=repair_dedupe_key(repo, number, head_sha),
            payload={
                "repo": repo,
                "number": number,
                "head_sha": head_sha,
                "installation_id": ctx.payload.get("installation_id"),
                "guard_job_id": str(ctx.job.id),
            },
            max_attempts=1,
            timeout_s=3600,
        )
    await ctx.emit("repair", f"repair job {job.id} {'queued' if created else 'already active'}")
    return {"enqueued": created, "job_id": str(job.id)}


@handler("repair.pr")
async def repair_pull_request(ctx: JobContext) -> dict[str, Any]:
    """Failing-test-first repair; opens a draft PR into the PR branch only if verified.
    Enqueued by guard.pr when FURNACE_GUARD_AUTO_REPAIR is on (that is the write consent).
    The full decision record is kept in the job result and events."""
    from furnace import cli
    from furnace.github import flows

    app, suite, questions = _runner_config()
    repo, number = ctx.payload["repo"], int(ctx.payload["number"])
    await ctx.emit("repair", f"Repairing {repo}#{number} at {str(ctx.payload['head_sha'])[:7]}")
    loop = asyncio.get_running_loop()

    pending: list[asyncio.Task[None]] = []

    def progress(msg: str) -> None:
        """Called from the repair thread (blocks until stored) and from the event loop
        itself (scheduled; blocking there would deadlock)."""
        stage = (msg.split(":", 1)[0] if ":" in msg else "repair")[:60]
        try:
            on_loop = asyncio.get_running_loop() is loop
        except RuntimeError:
            on_loop = False
        if on_loop:
            pending.append(loop.create_task(ctx.emit(stage, msg)))
        else:
            asyncio.run_coroutine_threadsafe(ctx.emit(stage, msg), loop).result(timeout=30)

    out = await flows.repair_pr(
        app,
        repo,
        number,
        suite=suite,
        target=cli._target(no_endpoint=False),
        questions=questions,
        open_pr=True,
        progress=progress,
        expected_head_sha=ctx.payload.get("head_sha"),
        expected_installation=ctx.payload.get("installation_id"),
    )
    await asyncio.gather(*pending)
    pr = out.get("pr") or {}
    await ctx.emit("repair", f"{out['status']}: {pr.get('url') or out.get('reason', '')}")
    return {k: v for k, v in out.items() if k != "files"}


@handler("guard.local")
async def guard_local(ctx: JobContext) -> dict[str, Any]:
    """Guard an F1 fixture PR scenario on this runner, without GitHub (live demo view)."""
    from furnace.guardian.live import run_local_guard

    scenario = str(ctx.payload["scenario"])
    emit = _thread_emitter(ctx, "guard")
    return await asyncio.to_thread(run_local_guard, scenario, emit)
