"""The live GitHub run, end to end, recorded as evidence.

  uv run python scripts/live_github_run.py --repo <you>/furnace-demo-f1

Prerequisites (docs/github-app.md): the App exists and is installed on the repository
(`furnace gh-setup`), the repository has `main` (F1) and `r1-request-id` (the R1 change)
pushed, the lab vLLM is up, the laptop is on AC.

Steps, each timed and recorded (stops at the first failing step; nothing after it is
claimed):
  1. check     App identity, permissions and the installation on the repository
  2. forge     plan + sandbox-validate F1, open the Forge draft PR
  3. r1_pr     find or open the R1 pull request (r1-request-id -> main), as its developer would
  4. guard     targeted checks on the R1 PR -> a Furnace Guard check run
  5. repair    failing test first, strategies, sandbox, perf gate -> draft repair PR
  6. replay    Forge and repair again on the same commits: must return the same PRs
               (reused=True), proving retries do not open duplicates on real GitHub

Output: bench/results/<UTC date>-live-github/live_run.{json,md}, with PR and check URLs.
Exit code 0 only if every step succeeded and Guard's conclusion was "failure" (R1 is a
known regression: a "success" would mean Guard missed it).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))

from common import manifest, write_json  # noqa: E402
from furnace import cli  # noqa: E402
from furnace.github import flows  # noqa: E402
from furnace.github.client import API, HEADERS, PR_PERMISSIONS, GitHubError  # noqa: E402

Q = ROOT / "fixtures/apps/support-rag-py/docs/facts.json"
SUITE = ROOT / "fixtures/scenarios/f1_suite.py"
WORKLOAD = ROOT / "bench/results/2026-10-04-f1-quality/workload-f1-traces-qwen05b.yaml"
R1_TITLE = "Add request id and timestamp to the system prompt for debugging"
R1_BODY = (
    "Opened by `scripts/live_github_run.py` on behalf of the change's developer, to exercise "
    "Furnace Guard on a real pull request. The change is the R1 scenario from FurnaceBench."
)


async def ensure_r1_pr(app: Any, repo: str, head: str, base: str) -> dict[str, Any]:
    """The open PR from `head` into `base`, or a new (non-draft) one."""
    writer = await flows._token(app, repo, PR_PERMISSIONS)
    owner = repo.split("/", 1)[0]
    async with httpx.AsyncClient(
        base_url=API, headers={**HEADERS, "Authorization": f"Bearer {writer.token}"}, timeout=30
    ) as c:
        r = await c.get(
            f"/repos/{repo}/pulls",
            params={"head": f"{owner}:{head}", "base": base, "state": "open"},
        )
        if r.status_code >= 400:
            raise GitHubError(f"list pulls: {r.status_code} {r.text[:200]}")
        if r.json():
            p = r.json()[0]
            return {"number": p["number"], "url": p["html_url"], "opened": False}
        r = await c.post(
            f"/repos/{repo}/pulls",
            json={"title": R1_TITLE, "head": head, "base": base, "body": R1_BODY},
        )
        if r.status_code >= 400:
            raise GitHubError(f"open R1 PR: {r.status_code} {r.text[:200]}")
        p = r.json()
        return {"number": p["number"], "url": p["html_url"], "opened": True}


def _strip(out: dict[str, Any]) -> dict[str, Any]:
    """Keep what a reviewer needs; drop file contents and bulky benchmark reports."""
    keep = {k: v for k, v in out.items() if k not in ("files", "results", "logs")}
    perf = keep.get("perf") or {}
    if perf:
        keep["perf"] = {
            "summary": perf.get("summary"),
            "reasons": perf.get("reasons"),
            "within_budget": perf.get("within_budget"),
            "head_vs_base": {
                k: v for k, v in (perf.get("head_vs_base") or {}).items() if k != "samples_ms"
            },
            "candidate_vs_base": {
                k: v for k, v in (perf.get("candidate_vs_base") or {}).items() if k != "samples_ms"
            },
        }
    return keep


def render(res: dict[str, Any]) -> str:
    lines = [
        "# Live GitHub run",
        "",
        f"Repository `{res['repo']}`, started {res['manifest']['started_at']}, code "
        f"`{(res['manifest']['git'].get('sha') or '')[:7]}` (dirty={res['manifest']['git'].get('dirty')}).",
        f"Result: **{res['verdict']}**.",
        "",
        "| step | ok | seconds | result |",
        "|---|---|---:|---|",
    ]
    for s in res["steps"]:
        o = s.get("out") or {}
        pr = o.get("pr") or {}
        detail = (
            s.get("error")
            or (pr.get("url") and f"{pr['url']} (reused={pr.get('reused')})")
            or o.get("url")
            or (o.get("conclusion") and f"{o['conclusion']}: {o.get('title')}")
            or o.get("reason")
            or o.get("status")
            or ""
        )
        lines.append(f"| {s['step']} | {'yes' if s['ok'] else 'NO'} | {s['seconds']} | {detail} |")
    return "\n".join(lines) + "\n"


async def main_async(a: argparse.Namespace) -> dict[str, Any]:
    app = cli._app()
    suite = cli._suite(str(SUITE))
    questions = cli._questions(str(Q))
    target = cli._target(no_endpoint=False)
    import yaml

    workload = yaml.safe_load(WORKLOAD.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = []
    say = lambda m: print(f"  {m}", flush=True)  # noqa: E731

    async def step(name: str, coro_fn: Any) -> dict[str, Any] | None:
        print(f"== {name}", flush=True)
        t0 = time.monotonic()
        rec: dict[str, Any] = {"step": name}
        try:
            out = await coro_fn()
            rec.update(ok=True, out=_strip(out) if isinstance(out, dict) else out)
        except Exception as exc:  # recorded, then the run stops
            rec.update(
                ok=False,
                error=f"{type(exc).__name__}: {str(exc)[:500]}",
                trace=traceback.format_exc()[-2000:],
            )
        rec["seconds"] = round(time.monotonic() - t0, 1)
        steps.append(rec)
        return rec.get("out") if rec["ok"] else None

    async def forge_once() -> dict[str, Any]:
        out = await flows.forge_pr(
            app, a.repo, questions=questions, workload=workload, open_pr=True, progress=say
        )
        if not out.get("pr"):  # validation failed or nothing to install: no PR is a failure here
            raise RuntimeError(f"no Forge PR: {out.get('reason')}")
        return out

    ok = True
    if await step("check", app.app_info) is None:
        ok = False
    forge = ok and await step("forge", forge_once)
    r1 = forge and await step("r1_pr", lambda: ensure_r1_pr(app, a.repo, a.head, a.base))
    pr_number = int(r1["number"]) if r1 else 0  # only used when r1 exists
    guard = r1 and await step(
        "guard",
        lambda: flows.guard_pr(
            app, a.repo, pr_number, suite=suite, target=target, questions=questions,
            max_prompt_tokens=3840, progress=say, rerun=True,
        ),
    )  # fmt: skip
    repair = guard and await step(
        "repair",
        lambda: flows.repair_pr(
            app, a.repo, pr_number, suite=suite, target=target, questions=questions,
            open_pr=True, progress=say,
        ),
    )  # fmt: skip
    if repair:
        await step("replay_forge", forge_once)
        if (repair.get("pr") or {}).get("number"):
            await step(
                "replay_repair",
                lambda: flows.repair_pr(
                    app, a.repo, pr_number, suite=suite, target=target, questions=questions,
                    open_pr=True, progress=say,
                ),
            )  # fmt: skip

    def pr_of(name: str) -> dict[str, Any]:
        s = next((s for s in steps if s["step"] == name and s["ok"]), None)
        return ((s or {}).get("out") or {}).get("pr") or {}

    checks = {
        "all_steps_ok": all(s["ok"] for s in steps) and len(steps) >= 5,
        "guard_flagged_r1": (guard or {}).get("conclusion") == "failure",
        "repair_verified": (repair or {}).get("status") == "verified",
        "forge_replay_same_pr": bool(pr_of("forge"))
        and pr_of("replay_forge").get("number") == pr_of("forge").get("number")
        and pr_of("replay_forge").get("reused") is True,
        "repair_replay_same_pr": not pr_of("repair")
        or (
            pr_of("replay_repair").get("number") == pr_of("repair").get("number")
            and pr_of("replay_repair").get("reused") is True
        ),
    }
    verdict = (
        "PASS"
        if all(checks.values())
        else "INCOMPLETE: " + ", ".join(k for k, v in checks.items() if not v)
    )
    return {"repo": a.repo, "steps": steps, "checks": checks, "verdict": verdict}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="owner/furnace-demo-f1")
    p.add_argument("--head", default="r1-request-id")
    p.add_argument("--base", default="main")
    a = p.parse_args()
    mf = manifest()
    res = asyncio.run(main_async(a))
    res = {"manifest": mf, **res}
    out = ROOT / "bench/results" / f"{dt.datetime.now(dt.UTC):%Y-%m-%d}-live-github"
    write_json(out / "live_run.json", res)
    (out / "live_run.md").write_text(render(res), encoding="utf-8")
    print(render(res))
    print(json.dumps(res["checks"], indent=2))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
