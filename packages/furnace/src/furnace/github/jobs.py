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
    if not s.guard_suite_path:
        raise RuntimeError("FURNACE_GUARD_SUITE_PATH is not set on this runner")
    repo, number = ctx.payload["repo"], int(ctx.payload["number"])
    await ctx.emit("guard", f"Guarding {repo}#{number}")
    out = await flows.guard_pr(
        cli._app(),
        repo,
        number,
        suite=cli._suite(str(s.guard_suite_path)),
        target=cli._target(no_endpoint=False),
        questions=cli._questions(str(s.guard_questions_path) if s.guard_questions_path else None),
        max_prompt_tokens=s.guard_max_prompt_tokens,
        on_event=_thread_emitter(ctx, "guard"),
    )
    await ctx.emit("guard", f"{out['conclusion']}: {out['title']}")
    return {"check_id": out["check_id"], "conclusion": out["conclusion"], "title": out["title"]}


@handler("guard.local")
async def guard_local(ctx: JobContext) -> dict[str, Any]:
    """Guard an F1 fixture PR scenario on this runner, without GitHub (live demo view)."""
    from furnace.guardian.live import run_local_guard

    scenario = str(ctx.payload["scenario"])
    emit = _thread_emitter(ctx, "guard")
    return await asyncio.to_thread(run_local_guard, scenario, emit)
