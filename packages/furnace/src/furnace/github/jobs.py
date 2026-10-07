"""Runner job: Guard a pull request when the GitHub webhook says it changed.

Enqueued by the API's webhook endpoint on the `runner` queue; executed by the laptop
runner (`uv run poe runner`), which has Docker, the lab endpoint and the App key.
"""

from __future__ import annotations

from typing import Any

from furnace.jobs.worker import JobContext, handler
from furnace.settings import get_settings


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
    )
    await ctx.emit("guard", f"{out['conclusion']}: {out['title']}")
    return {"check_id": out["check_id"], "conclusion": out["conclusion"], "title": out["title"]}
