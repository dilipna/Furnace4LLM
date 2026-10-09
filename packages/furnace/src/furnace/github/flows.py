"""End-to-end GitHub flows run by the laptop runner: Guard a pull request (check run),
open a Forge draft PR, and open a verified repair draft PR.

Each flow mints its own installation token with only the permissions it needs, reads
revisions as tarballs into a temporary directory (safe extraction), runs the existing
reconstruction / Forge / Guard / repair code, and writes back only a check run or a
draft pull request. Nothing is merged; nothing is pushed to a default branch.
Pull requests from forks are refused: their code would run in the sandbox with access
to the lab endpoint, which is a decision for a human, not a default.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from furnace_bench.schema import BenchTarget

from furnace.blueprint.rules import run_rules
from furnace.contracts.guard import ForgePlan
from furnace.forge.harness import write_harness
from furnace.forge.planner import Planner
from furnace.forge.validate import ForgeValidation, validate
from furnace.github.client import (
    GUARD_PERMISSIONS,
    PR_PERMISSIONS,
    SCAN_PERMISSIONS,
    GitHubApp,
    GitHubError,
    Repo,
)
from furnace.guardian.execute import GuardContext, prepare, run_items, selected_items, verdict
from furnace.guardian.impact import SuiteItem, analyze_impact, analyze_tree
from furnace.guardian.live import impact_event
from furnace.guardian.perf_gate import GatePolicy, compare, run_gate
from furnace.guardian.repair.loop import repair_prefix_instability
from furnace.guardian.repair.regression import min_shared_prefix, render_in_sandbox
from furnace.guardian.report import check_run, repair_pr_body
from furnace.ingest.sources import GitHubRef, download_github_tarball
from furnace.reconstruction.build import reconstruct
from furnace.security.safe_extract import ExtractLimits, safe_extract_tar

Progress = Callable[[str], None]


def _say(progress: Progress | None, msg: str) -> None:
    if progress:
        progress(msg)


async def _token(app: GitHubApp, full_name: str, permissions: dict[str, str]) -> Repo:
    inst = await app.installation_for(full_name)
    token = await app.installation_token(
        inst, repository=full_name.split("/", 1)[1], permissions=permissions
    )
    return Repo(full_name, token, transport=app.transport)


async def fetch_revision(full_name: str, sha: str, token: str, dest: Path) -> Path:
    """Download `owner/name@sha` and extract it safely into `dest`."""
    owner, name = full_name.split("/", 1)
    tarball = dest.parent / f"{dest.name}.tar.gz"
    await download_github_tarball(GitHubRef(owner, name), sha, tarball, token)

    def extract() -> None:  # blocking file work stays off the event loop
        safe_extract_tar(tarball, dest, ExtractLimits(), strip_components=1)
        tarball.unlink(missing_ok=True)

    await asyncio.to_thread(extract)
    return dest


async def _pull(repo: Repo, number: int) -> dict[str, Any]:
    pr = await repo.pull(number)
    if pr["head_repo"] != repo.full_name:
        raise GitHubError(
            f"PR #{number} comes from a fork ({pr['head_repo']}); Furnace does not run fork code by default"
        )
    return pr


# ---------------------------------------------------------------------------------- Guard


async def guard_pr(
    app: GitHubApp,
    full_name: str,
    number: int,
    *,
    suite: list[SuiteItem],
    target: BenchTarget | None,
    questions: list[str],
    max_prompt_tokens: int | None = None,
    progress: Progress | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the graph-targeted checks for PR `number` and report them as a check run.

    `on_event` (called from a worker thread) receives the structured impact/check events
    the live Guard view draws; see furnace.guardian.live."""
    repo = await _token(app, full_name, GUARD_PERMISSIONS)
    pr = await _pull(repo, number)
    check_id = await repo.create_check(pr["head_sha"])
    _say(progress, f"check run {check_id} started on {pr['head_sha'][:7]}")
    tmp = Path(tempfile.mkdtemp(prefix="furnace-guard-pr-"))
    try:
        base_root = await fetch_revision(full_name, pr["base_sha"], repo.token, tmp / "base")
        head_root = await fetch_revision(full_name, pr["head_sha"], repo.token, tmp / "head")
        head_state = await asyncio.to_thread(analyze_tree, head_root)
        impact = await asyncio.to_thread(
            lambda: analyze_impact(
                analyze_tree(base_root),
                head_state,
                suite,
                pr_number=number,
                base_sha=pr["base_sha"],
                head_sha=pr["head_sha"],
            )
        )
        if on_event:  # the emitter blocks until stored: keep it off the event loop
            await asyncio.to_thread(on_event, impact_event(impact, head_state))
        items = selected_items(impact, suite)
        _say(
            progress,
            f"impact: {len(items)}/{len(suite)} checks selected ({', '.join(sorted(impact.categories)) or 'no categories'})",
        )
        work, base, head = await asyncio.to_thread(prepare, base_root, head_root)
        try:
            ctx = GuardContext(
                base=base,
                head=head,
                questions=questions,
                target=target,
                max_prompt_tokens=max_prompt_tokens,
            )
            results = await asyncio.to_thread(
                run_items, items, ctx, lambda m: _say(progress, m), on_event
            )
        finally:
            shutil.rmtree(work, ignore_errors=True)
        cr = check_run(impact, results, verdict(results))
        await repo.complete_check(
            check_id,
            conclusion=cr["conclusion"],
            title=cr["title"],
            summary=cr["summary"],
            text=cr["text"],
            annotations=cr["annotations"],
        )
        _say(progress, f"check run completed: {cr['conclusion']} ({cr['title']})")
        if on_event:
            verdict_ev = {"type": "verdict", "conclusion": cr["conclusion"], "title": cr["title"]}
            await asyncio.to_thread(on_event, verdict_ev)
        return {
            "check_id": check_id,
            "conclusion": cr["conclusion"],
            "title": cr["title"],
            "results": [r.__dict__ for r in results],
        }
    except Exception as exc:
        # Never leave a check spinning: report the failure honestly as neutral.
        await repo.complete_check(
            check_id,
            conclusion="neutral",
            title="Furnace Guard could not complete",
            summary=f"{type(exc).__name__}: {str(exc)[:500]}",
        )
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------- Forge


def forge_pr_body(plan: ForgePlan, v: ForgeValidation, skipped: list[dict[str, str]]) -> str:
    rows = [
        f"| `{c.path}` | {c.change_type.value} | {c.reason} | {c.target} | {c.risk} |"
        for c in plan.changes
    ]
    lines = [
        "## Furnace Forge: reliability layer (draft, human review required)",
        "",
        "Every file below exists because a Blueprint finding justified it.",
        "",
        "| file | change | why | serves | risk |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "### Validation (sandboxed, before this PR was opened)",
        f"- prompts byte-identical after extraction: **{v.prompts_identical}**",
        f"- installed tests: **{v.installed_tests}**",
        f"- existing tests: **{v.existing_tests}**",
        f"- findings resolved: {', '.join(v.resolved_findings) or 'none'}",
        f"- findings still open: {', '.join(v.remaining_findings) or 'none'}",
    ]
    if skipped:
        lines += [
            "",
            "### Not installed",
            *[f"- `{s.get('rule_id')}`: {s.get('reason')}" for s in skipped],
        ]
    lines += ["", "Furnace never merges. Review the diff, then merge or close."]
    return "\n".join(lines)


async def forge_pr(
    app: GitHubApp,
    full_name: str,
    *,
    questions: list[str],
    workload: dict[str, Any] | None = None,
    open_pr: bool = False,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Plan and validate the Forge change set on the default branch; open a draft PR only
    when validation passes and `open_pr` (explicit write consent) is set."""
    repo = await _token(app, full_name, SCAN_PERMISSIONS)
    branch, sha = await repo.default_branch()
    tmp = Path(tempfile.mkdtemp(prefix="furnace-forge-pr-"))
    try:
        root = await fetch_revision(full_name, sha, repo.token, tmp / "src")
        _say(progress, f"fetched {full_name}@{sha[:7]} ({branch})")

        def plan_and_validate() -> tuple[Any, ForgeValidation]:
            rec = reconstruct(root)
            recs = run_rules(rec)
            shared = None
            probe = Path(shutil.copytree(root, tmp / "probe"))
            try:  # measure the shared prompt prefix through the app's own handler, sandboxed
                write_harness(reconstruct(probe))
                shared = min_shared_prefix(render_in_sandbox(probe, questions[:4]))
            except Exception:  # no sliceable prompt path: the prefix test is not installed
                shared = None
            result = Planner(
                rec, recs, questions=questions, workload=workload, default_branch=branch
            ).run(shared_prefix=shared)
            return result, validate(root, result, questions)

        result, v = await asyncio.to_thread(plan_and_validate)
        _say(progress, f"planned {len(result.files)} files; validation ok={v.ok}")
        out: dict[str, Any] = {"files": sorted(result.files), "validation": v.as_dict(), "pr": None}
        if not v.ok:
            out["reason"] = "validation failed; no pull request opened"
            return out
        if not open_pr:
            out["reason"] = "dry run (pass --open-pr to open a draft pull request)"
            return out
        writer = await _token(app, full_name, PR_PERMISSIONS)
        out["pr"] = await writer.open_draft_pr(
            base_branch=branch,
            new_branch=f"furnace/forge-{sha[:7]}",
            files=result.files,
            title="Furnace Forge: evals, tracing hooks and benchmark configs",
            body=forge_pr_body(result.plan, v, result.skipped),
            commit_message="Furnace Forge: install the reliability layer justified by the Blueprint",
            base_sha=sha,
        )
        _say(progress, f"draft PR opened: {out['pr']['url']}")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------- Repair


async def repair_pr(
    app: GitHubApp,
    full_name: str,
    number: int,
    *,
    suite: list[SuiteItem],
    target: BenchTarget | None,
    questions: list[str],
    open_pr: bool = False,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Failing-test-first repair of a prefix-instability regression in PR `number`. Opens a
    draft PR into the PR's branch only when the repair is verified and `open_pr` is set."""
    repo = await _token(app, full_name, GUARD_PERMISSIONS)
    pr = await _pull(repo, number)
    tmp = Path(tempfile.mkdtemp(prefix="furnace-repair-pr-"))
    try:
        base_root = await fetch_revision(full_name, pr["base_sha"], repo.token, tmp / "base")
        head_root = await fetch_revision(full_name, pr["head_sha"], repo.token, tmp / "head")
        policy = GatePolicy()

        def perf_check(base: Path, head: Path, cand: Path) -> dict[str, Any]:
            assert target is not None
            res = run_gate(
                {"base": base, "pr_head": head, "candidate": cand}, questions, target, concurrency=8
            )
            hv, cv = (
                compare(res["base"], res["pr_head"], policy),
                compare(res["base"], res["candidate"], policy),
            )
            return {
                "head_vs_base": hv,
                "candidate_vs_base": cv,
                "within_budget": cv["verdict"] in ("pass", "warn"),
                "summary": f"p95 TTFT base {hv['baseline']} | PR {hv['value']} ({hv['change_pct']:+}%) | repair {cv['value']} ({cv['change_pct']:+}%)",
            }

        def run() -> Any:
            impact = analyze_impact(
                analyze_tree(base_root),
                analyze_tree(head_root),
                suite,
                pr_number=number,
                base_sha=pr["base_sha"],
                head_sha=pr["head_sha"],
            )
            return repair_prefix_instability(
                base_root,
                head_root,
                impact,
                questions=questions[:6],
                change_label=f"PR #{number}",
                progress=lambda stage, msg: _say(progress, f"{stage}: {msg}"),
                perf_check=perf_check if target is not None else None,
            )

        outcome = await asyncio.to_thread(run)
        status = outcome.attempt.status.value
        out: dict[str, Any] = {
            "status": status,
            "logs": outcome.logs,
            "perf": outcome.perf,
            "pr": None,
        }
        if status != "verified" or not outcome.files:
            out["reason"] = "no verified repair; nothing opened"
            return out
        if not open_pr:
            out["reason"] = "dry run (pass --open-pr to open a draft pull request)"
            out["files"] = sorted(outcome.files)
            return out
        explanation = (
            outcome.attempt.candidates[0].results.get("explanation")
            if outcome.attempt.candidates
            else ""
        ) or ""
        writer = await _token(app, full_name, PR_PERMISSIONS)
        out["pr"] = await writer.open_draft_pr(
            base_branch=pr["head_ref"],
            new_branch=f"furnace/repair-pr{number}-{pr['head_sha'][:7]}",
            files=outcome.files,
            title=f"Furnace repair for #{number}: keep the prompt prefix stable",
            body=repair_pr_body(outcome.attempt, outcome.perf, explanation, outcome.test_path),
            commit_message=f"Furnace repair for #{number}: regression test first, then the fix",
            base_sha=pr["head_sha"],
        )
        _say(progress, f"draft repair PR opened: {out['pr']['url']}")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
