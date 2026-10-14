"""A fresh commit's signed webhook queues and completes a new Guard job: recorded as evidence.

  uv run python scripts/live_webhook_run.py --repo <you>/furnace-demo-f1 \
      [--demo-dir C:/dev/furnace-demo-f1] [--from r1-request-id]

Closes the gap left by scripts/live_github_run.py, where the webhook-queued job found the
head already checked and reused that check run. Here the head commit is new, so nothing
can be reused. Prerequisites: the API (:8010) with the App's webhook secret, the App's
deliveries forwarded to it (smee-client), the Guard runner and the lab vLLM up.

Steps (each read from GitHub or the database, never from the runner's own report):
  1. commit     a new commit on a new branch made from --from, pushed with the owner's git
                credentials (the App never pushes to a user's branch)
  2. pr         a non-draft PR from that branch into main, opened with the App's PR token
                (as scripts/live_github_run.py opened the R1 PR)
  3. delivery   GitHub's pull_request/opened delivery for that PR, and its row in
                webhook_deliveries: source=push (HMAC-verified), outcome=queued, a job id
  4. redeliver  GitHub redelivers the same GUID while the job is active: no new delivery
                or job row (duplicate handling)
  5. job        the guard.pr job reaches a terminal state on the runner
  6. check      Furnace's check runs on the new head SHA: exactly one, by this App,
                head_sha equal to the commit from step 1, completed
  7. redeliver  again after completion: still no new rows and still one check run

The Guard conclusion is recorded as it comes; the branch carries the R1 regression, so
"failure" is the expected verdict, but a different one is reported, not rerun.
Output: bench/results/<UTC date>-live-webhook/webhook_run.{json,md}. Exit code 0 only if
every step passed (the event path worked), whatever Guard concluded.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))

from common import manifest, write_json  # noqa: E402
from furnace import cli  # noqa: E402
from furnace.github import flows  # noqa: E402
from furnace.github.client import API, HEADERS, PR_PERMISSIONS, app_jwt  # noqa: E402
from furnace.github.events import guard_dedupe_key  # noqa: E402

PR_TITLE = "Webhook re-check: note the request-id change in the README"
PR_BODY = (
    "Opened by `scripts/live_webhook_run.py` to show a fresh head commit's signed webhook "
    "queuing a new Furnace Guard run. The branch is the R1 change plus one README line."
)
TERMINAL = {"succeeded", "failed", "cancelled"}


class StepFailed(Exception):
    pass


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)  # noqa: S603, S607
    if r.returncode != 0:
        raise StepFailed(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def _utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


async def db_counts(guid: str, dedupe_key: str) -> dict[str, int]:
    from furnace.db.models import Job, WebhookDelivery
    from furnace.db.session import session_scope
    from sqlalchemy import func, select

    async with session_scope() as s:
        d = await s.scalar(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.delivery_id == guid)
        )
        j = await s.scalar(
            select(func.count()).select_from(Job).where(Job.dedupe_key == dedupe_key)
        )
        g = await s.scalar(select(func.count()).select_from(Job).where(Job.kind == "guard.pr"))
    return {"delivery_rows": int(d or 0), "jobs_for_head": int(j or 0), "guard_jobs": int(g or 0)}


async def main_async(a: argparse.Namespace) -> dict[str, Any]:
    from furnace.db.models import Job, WebhookDelivery
    from furnace.db.session import session_scope

    app = cli._app()
    started = dt.datetime.now(dt.UTC)
    res: dict[str, Any] = {"manifest": manifest(repo=a.repo, from_branch=a.from_), "steps": []}
    st: dict[str, Any] = {}

    def jwt() -> httpx.AsyncClient:
        tok = app_jwt(app.app_id, app.private_key_pem)
        return httpx.AsyncClient(
            base_url=API, headers={**HEADERS, "Authorization": f"Bearer {tok}"}, timeout=30
        )

    async def step(name: str, fn: Any) -> bool:
        t0 = time.monotonic()
        print(f"-- {name}", flush=True)
        try:
            out = await fn()
            rec = {"step": name, "ok": True, "out": out}
        except Exception as exc:  # recorded, never swallowed
            rec = {"step": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:600]}
        rec["seconds"] = round(time.monotonic() - t0, 1)
        res["steps"].append(rec)
        print(
            f"   {'ok' if rec['ok'] else 'FAIL'} {rec.get('out') or rec.get('error')}", flush=True
        )
        return rec["ok"]

    async def commit() -> dict[str, Any]:
        d = Path(a.demo_dir)
        if git(d, "status", "--porcelain"):
            raise StepFailed(f"{d} has uncommitted changes")
        git(d, "fetch", "origin")
        branch = a.branch or f"webhook-recheck-{started:%Y%m%d-%H%M}"
        base = git(d, "rev-parse", f"origin/{a.from_}")
        git(d, "switch", "-c", branch, base)
        try:
            readme = d / "README.md"
            text = readme.read_text(encoding="utf-8") if readme.exists() else ""
            note = (
                f"\nThe system prompt now carries a request id and timestamp for debugging "
                f"(re-check {started:%Y-%m-%d %H:%M} UTC).\n"
            )
            readme.write_text(text + note, encoding="utf-8")
            git(d, "add", "README.md")
            git(d, "commit", "-q", "-m", "README: note the request id in the system prompt")
            sha = git(d, "rev-parse", "HEAD")
            git(d, "push", "-q", "origin", f"{branch}:refs/heads/{branch}")
        finally:
            git(d, "switch", "-q", "main")
        st.update(branch=branch, sha=sha)
        return {"branch": branch, "parent": base, "head_sha": sha}

    async def pr() -> dict[str, Any]:
        writer = await flows._token(app, a.repo, PR_PERMISSIONS)
        async with httpx.AsyncClient(
            base_url=API, headers={**HEADERS, "Authorization": f"Bearer {writer.token}"}, timeout=30
        ) as c:
            r = await c.post(
                f"/repos/{a.repo}/pulls",
                json={"title": PR_TITLE, "head": st["branch"], "base": "main", "body": PR_BODY},
            )
        if r.status_code >= 400:
            raise StepFailed(f"open PR: {r.status_code} {r.text[:200]}")
        p = r.json()
        if p["head"]["sha"] != st["sha"]:
            raise StepFailed(f"PR head {p['head']['sha']} != pushed {st['sha']}")
        st.update(number=p["number"], dedupe=guard_dedupe_key(a.repo, p["number"], st["sha"]))
        return {"number": p["number"], "url": p["html_url"], "draft": p["draft"]}

    async def delivery() -> dict[str, Any]:
        deadline = time.monotonic() + a.delivery_wait
        async with jwt() as c:
            while time.monotonic() < deadline:
                dl = (await c.get("/app/hook/deliveries", params={"per_page": 50})).json()
                for d in dl:
                    if (
                        d.get("event") == "pull_request"
                        and d.get("action") == "opened"
                        and not d.get("redelivery")
                        and _utc(d["delivered_at"]) >= started - dt.timedelta(seconds=5)
                    ):
                        full = (await c.get(f"/app/hook/deliveries/{d['id']}")).json()
                        payload = (full.get("request") or {}).get("payload") or {}
                        if (payload.get("pull_request") or {}).get("number") == st["number"]:
                            st.update(delivery_id=d["id"], guid=d["guid"])
                            break
                if "guid" in st:
                    break
                await asyncio.sleep(3)
        if "guid" not in st:
            raise StepFailed(f"no pull_request/opened delivery for #{st['number']} in GitHub's log")
        row = None
        while time.monotonic() < deadline and row is None:
            async with session_scope() as s:
                row = await s.get(WebhookDelivery, st["guid"])
            if row is None:
                await asyncio.sleep(2)
        if row is None:
            raise StepFailed(f"delivery {st['guid']} never reached the receiver")
        problems = []
        if row.source != "push":
            problems.append(f"recorded via {row.source}, not over HMAC (push)")
        if row.outcome != "queued" or row.job_id is None:
            problems.append(f"outcome {row.outcome!r} ({row.detail}), job {row.job_id}")
        if problems:
            raise StepFailed("; ".join(problems))
        st["job_id"] = row.job_id
        return {
            "guid": st["guid"],
            "github_status_code": d.get("status_code"),
            "delivered_at": d.get("delivered_at"),
            "source": row.source,
            "outcome": row.outcome,
            "job_id": str(row.job_id),
        }

    async def redeliver(when: str) -> dict[str, Any]:
        async with session_scope() as s:
            job = await s.get(Job, st["job_id"])
            job_status = job.status if job else None
        before = await db_counts(st["guid"], st["dedupe"])
        async with jwt() as c:
            r = await c.post(f"/app/hook/deliveries/{st['delivery_id']}/attempts")
            if r.status_code >= 300:
                raise StepFailed(f"redelivery request refused: {r.status_code} {r.text[:200]}")
            again: list[dict[str, Any]] = []
            deadline = time.monotonic() + a.redeliver_wait
            while time.monotonic() < deadline:
                await asyncio.sleep(3)
                dl = (await c.get("/app/hook/deliveries", params={"per_page": 50})).json()
                again = [x for x in dl if x["guid"] == st["guid"] and x.get("redelivery")]
                if len(again) > st.get("redeliveries", 0):
                    break
        st["redeliveries"] = len(again)
        await asyncio.sleep(2)
        after = await db_counts(st["guid"], st["dedupe"])
        if not again:
            raise StepFailed("GitHub shows no redelivery attempt")
        code = again[0].get("status_code")
        if code not in (200, 202):
            raise StepFailed(f"receiver answered the redelivery with {code}")
        if after != before:
            raise StepFailed(f"rows changed on redelivery: {before} -> {after}")
        return {
            "when": when,
            "job_status_at_redelivery": job_status,
            "redelivery_status_code": code,
            "rows_before": before,
            "rows_after": after,
        }

    async def job() -> dict[str, Any]:
        deadline = time.monotonic() + a.job_timeout
        seen: list[str] = []
        while time.monotonic() < deadline:
            async with session_scope() as s:
                j = await s.get(Job, st["job_id"])
            if j.status not in seen:
                seen.append(j.status)
                print(f"   job {j.status}", flush=True)
            if j.status in TERMINAL:
                break
            await asyncio.sleep(5)
        else:
            raise StepFailed(f"job not finished after {a.job_timeout}s (states {seen})")
        result = j.result or {}
        out = {
            "job_id": str(j.id),
            "status": j.status,
            "states_seen": seen,
            "attempts": j.attempts,
            "locked_by": j.locked_by,
            "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "seconds": (j.finished_at - j.created_at).total_seconds() if j.finished_at else None,
            "error": j.error,
            "result": {k: v for k, v in result.items() if k not in ("report", "checks_detail")},
        }
        if j.status != "succeeded":
            raise StepFailed(f"job {j.status}: {j.error}")
        st["result"] = result
        return out

    async def check() -> dict[str, Any]:
        reader = await flows._token(app, a.repo, {"checks": "read", "metadata": "read"})
        async with httpx.AsyncClient(
            base_url=API, headers={**HEADERS, "Authorization": f"Bearer {reader.token}"}, timeout=30
        ) as c:
            r = await c.get(f"/repos/{a.repo}/commits/{st['sha']}/check-runs")
        r.raise_for_status()
        runs = [
            x
            for x in r.json()["check_runs"]
            if str((x.get("app") or {}).get("id")) == str(app.app_id)
        ]
        if len(runs) != 1:
            raise StepFailed(f"{len(runs)} Furnace check runs on {st['sha'][:7]}, expected 1")
        cr = runs[0]
        problems = []
        if cr["head_sha"] != st["sha"]:
            problems.append(f"check head_sha {cr['head_sha']} != {st['sha']}")
        if cr["status"] != "completed" or not cr.get("completed_at"):
            problems.append(f"check status {cr['status']}")
        if problems:
            raise StepFailed("; ".join(problems))
        return {
            "check_run_id": cr["id"],
            "url": cr["html_url"],
            "head_sha": cr["head_sha"],
            "app": (cr.get("app") or {}).get("slug"),
            "conclusion": cr["conclusion"],
            "title": (cr.get("output") or {}).get("title"),
            "started_at": cr.get("started_at"),
            "completed_at": cr.get("completed_at"),
            "annotations": (cr.get("output") or {}).get("annotations_count"),
        }

    for name, fn in (
        ("commit", commit),
        ("pr", pr),
        ("delivery", delivery),
        ("redeliver_active", lambda: redeliver("while the job was active")),
        ("job", job),
        ("check", check),
        ("redeliver_done", lambda: redeliver("after the job completed")),
        ("check_after_redelivery", check),
    ):
        if not await step(name, fn):
            break
    res["ok"] = len(res["steps"]) == 8 and all(s["ok"] for s in res["steps"])
    res["finished_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    return res


def render(res: dict[str, Any]) -> str:
    m = res["manifest"]
    lines = [
        f"# Fresh-commit webhook run ({m['started_at']})",
        "",
        f"Repository `{m['repo']}`, branch made from `{m['from_branch']}`, code "
        f"{m['git'].get('sha', '')[:7]}. Result: **{'PASS' if res['ok'] else 'INCOMPLETE'}**.",
        "",
        "| step | ok | seconds | detail |",
        "|---|---|---|---|",
    ]
    for s in res["steps"]:
        detail = s.get("out") or s.get("error")
        lines.append(f"| {s['step']} | {s['ok']} | {s['seconds']} | `{detail}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--repo", required=True)
    p.add_argument("--demo-dir", default="C:/dev/furnace-demo-f1")
    p.add_argument("--from", dest="from_", default="r1-request-id")
    p.add_argument("--branch", default=None)
    p.add_argument("--delivery-wait", type=int, default=120)
    p.add_argument("--redeliver-wait", type=int, default=60)
    p.add_argument("--job-timeout", type=int, default=1800)
    p.add_argument("--out", default=None)
    a = p.parse_args()
    res = asyncio.run(main_async(a))
    out = (
        Path(a.out)
        if a.out
        else ROOT / "bench" / "results" / f"{res['manifest']['date']}-live-webhook"
    )
    write_json(out / "webhook_run.json", res)
    (out / "webhook_run.md").write_text(render(res), encoding="utf-8")
    print(f"wrote {out}", flush=True)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
