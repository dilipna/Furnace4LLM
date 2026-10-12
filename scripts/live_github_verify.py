"""Verify the live GitHub run against real GitHub, property by property.

  uv run python scripts/live_github_verify.py --repo <you>/furnace-demo-f1 \
      [--run bench/results/<date>-live-github/live_run.json] [--api http://localhost:8010]

Run after scripts/live_github_run.py. Every check reads GitHub (or the local receiver) and
records what it saw; nothing here trusts the run's own report. Checks:

  permissions       the App's permissions and events equal the manifest's, exactly; the
                    installation is limited to selected repositories, this one included
  token_scope       a read-only job token cannot create a branch or a check run (403); if
                    GitHub ever accepted, the probe branch is deleted and the check FAILS
  attribution       the Guard check run is on the R1 PR's current head commit, by this App
  check_updates     that check run went from started to completed, with output and annotations
  draft_prs         Forge and repair PRs are drafts from furnace/* branches, by the App; the
                    repair PR targets the R1 branch and is built on the R1 head commit
  branches_intact   main and the R1 branch are where they were before the run (Furnace never
                    pushes to a user's branch)
  no_duplicates     one open Furnace PR per purpose; the replays returned the same PRs
  webhook_*         (with --api, the receiver running with the App's webhook secret and the
                    App's deliveries forwarded to it) real GitHub deliveries were accepted
                    over HMAC (source=push), a GitHub redelivery of the same GUID is a no-op,
                    and forged or unsigned requests are refused (401)

A check that cannot run (e.g. no --api) is recorded as "not run" with the reason, never as
passed. Output: <run dir>/verify.{json,md}; exit code 0 only if every check that ran passed
and none of the core checks (all but webhook_*) was skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))

from common import manifest, write_json  # noqa: E402
from furnace import cli  # noqa: E402
from furnace.github import flows  # noqa: E402
from furnace.github.client import (  # noqa: E402
    API,
    GUARD_PERMISSIONS,
    HEADERS,
    PR_PERMISSIONS,
    SCAN_PERMISSIONS,
    app_jwt,
)
from furnace.github.setup import APP_EVENTS, APP_PERMISSIONS  # noqa: E402

CORE = (
    "permissions",
    "token_scope",
    "attribution",
    "check_updates",
    "draft_prs",
    "branches_intact",
    "no_duplicates",
)


# ------------------------------------------------------------------ pure checks (tested)


def check_permissions(app: dict[str, Any], installation: dict[str, Any], repo: str) -> list[str]:
    """Problems with the App's grant; empty means it is exactly what the manifest asks."""
    out = []
    perms = app.get("permissions") or {}
    if perms != APP_PERMISSIONS:
        extra = {k: v for k, v in perms.items() if APP_PERMISSIONS.get(k) != v}
        missing = {k: v for k, v in APP_PERMISSIONS.items() if perms.get(k) != v}
        out.append(
            f"permissions differ from the manifest: extra/changed {extra}, missing {missing}"
        )
    if sorted(app.get("events") or []) != sorted(APP_EVENTS):
        out.append(f"events {app.get('events')} != {APP_EVENTS}")
    if installation.get("repository_selection") != "selected":
        out.append(
            f"installation covers {installation.get('repository_selection')!r} repositories, "
            "not 'selected'"
        )
    if repo not in (installation.get("repositories") or []):
        out.append(f"{repo} is not among the installation's repositories")
    return out


def check_draft_pr(pr: dict[str, Any], *, base_ref: str, built_on: str | None) -> list[str]:
    """Problems with a Furnace PR: must be a draft from furnace/*, opened by a bot."""
    out = []
    if pr.get("draft") is not True:
        out.append(f"PR #{pr.get('number')} is not a draft")
    head = (pr.get("head") or {}).get("ref", "")
    if not head.startswith("furnace/"):
        out.append(f"PR #{pr.get('number')} head branch {head!r} is not under furnace/")
    if (pr.get("base") or {}).get("ref") != base_ref:
        out.append(f"PR #{pr.get('number')} targets {pr['base']['ref']!r}, expected {base_ref!r}")
    if (pr.get("user") or {}).get("type") != "Bot":
        out.append(f"PR #{pr.get('number')} was opened by {pr.get('user', {}).get('login')!r}")
    if built_on and pr.get("_first_parent") != built_on:
        out.append(
            f"PR #{pr.get('number')} is built on {str(pr.get('_first_parent'))[:7]}, "
            f"expected the R1 head {built_on[:7]}"
        )
    return out


def check_run_problems(run: dict[str, Any], *, head_sha: str, app_id: str) -> list[str]:
    out = []
    if run.get("head_sha") != head_sha:
        out.append(f"check run is on {str(run.get('head_sha'))[:7]}, PR head is {head_sha[:7]}")
    if str((run.get("app") or {}).get("id")) != str(app_id):
        out.append(f"check run belongs to app {(run.get('app') or {}).get('id')}, not {app_id}")
    if run.get("status") != "completed":
        out.append(f"check run status is {run.get('status')!r}")
    return out


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ------------------------------------------------------------------------- live checks


class GH:
    def __init__(self, token: str) -> None:
        self.c = httpx.AsyncClient(
            base_url=API, headers={**HEADERS, "Authorization": f"Bearer {token}"}, timeout=30
        )

    async def get(self, path: str, **kw: Any) -> Any:
        r = await self.c.get(path, **kw)
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self.c.aclose()


async def verify(a: argparse.Namespace, run: dict[str, Any]) -> dict[str, Any]:
    app = cli._app()
    steps = {s["step"]: s for s in run["steps"]}

    def out_of(step: str) -> dict[str, Any]:
        s = steps.get(step) or {}
        return (s.get("out") or {}) if s.get("ok") else {}

    results: list[dict[str, Any]] = []

    async def check(name: str, fn: Callable[[], Awaitable[tuple[list[str], dict[str, Any]]]]):
        t0 = time.monotonic()
        try:
            problems, seen = await fn()
            rec = {"check": name, "ok": not problems, "problems": problems, "seen": seen}
        except NotRun as nr:
            rec = {"check": name, "ok": None, "problems": [], "seen": {"not_run": str(nr)}}
        except Exception as exc:  # recorded as a failure, never swallowed
            rec = {"check": name, "ok": False, "problems": [f"{type(exc).__name__}: {exc}"[:400]]}
        rec["seconds"] = round(time.monotonic() - t0, 1)
        results.append(rec)
        print(f"{name}: {'not run' if rec['ok'] is None else 'ok' if rec['ok'] else 'FAIL'} "
              f"{rec['problems'] or ''}", flush=True)  # fmt: skip

    jwt_gh = GH(app_jwt(app.app_id, app.private_key_pem))
    reader = await flows._token(app, a.repo, GUARD_PERMISSIONS)
    gh = GH(reader.token)
    r1_number = int(out_of("r1_pr").get("number") or 0)
    guard = out_of("guard")
    forge_pr = (out_of("forge").get("pr") or {}).get("number")
    repair_pr = (out_of("repair").get("pr") or {}).get("number")

    async def permissions() -> tuple[list[str], dict[str, Any]]:
        info = await jwt_gh.get("/app")
        inst = await jwt_gh.get(f"/repos/{a.repo}/installation")
        tok = await flows._token(app, a.repo, SCAN_PERMISSIONS)
        ig = GH(tok.token)
        try:
            repos = await ig.get("/installation/repositories", params={"per_page": 100})
        finally:
            await ig.aclose()
        inst_view = {
            "repository_selection": inst.get("repository_selection"),
            "repositories": [r["full_name"] for r in repos.get("repositories", [])],
        }
        seen = {"permissions": info.get("permissions"), "events": info.get("events"), **inst_view}
        return check_permissions(info, inst_view, a.repo), seen

    async def token_scope() -> tuple[list[str], dict[str, Any]]:
        main_sha = (await gh.get(f"/repos/{a.repo}/git/ref/heads/main"))["object"]["sha"]
        probe = f"furnace/scope-probe-{uuid.uuid4().hex[:8]}"
        problems, seen = [], {}
        for label, perms in (("scan", SCAN_PERMISSIONS), ("guard", GUARD_PERMISSIONS)):
            t = await flows._token(app, a.repo, perms)
            async with httpx.AsyncClient(
                base_url=API, headers={**HEADERS, "Authorization": f"Bearer {t.token}"}, timeout=30
            ) as c:
                r = await c.post(
                    f"/repos/{a.repo}/git/refs",
                    json={"ref": f"refs/heads/{probe}", "sha": main_sha},
                )
                seen[f"{label}_token_create_branch"] = r.status_code
                if r.status_code < 300:
                    problems.append(f"{label} token could create a branch")
                    w = await flows._token(app, a.repo, PR_PERMISSIONS)
                    async with httpx.AsyncClient(
                        base_url=API,
                        headers={**HEADERS, "Authorization": f"Bearer {w.token}"},
                        timeout=30,
                    ) as wc:
                        await wc.delete(f"/repos/{a.repo}/git/refs/heads/{probe}")
                if label == "scan":
                    r = await c.post(
                        f"/repos/{a.repo}/check-runs",
                        json={"name": "furnace scope probe", "head_sha": main_sha},
                    )
                    seen["scan_token_create_check_run"] = r.status_code
                    if r.status_code < 300:
                        problems.append("scan token could create a check run")
        return problems, seen

    async def attribution() -> tuple[list[str], dict[str, Any]]:
        if not r1_number or not guard.get("check_id"):
            raise NotRun("the run has no R1 PR or Guard check run")
        pr = await gh.get(f"/repos/{a.repo}/pulls/{r1_number}")
        cr = await gh.get(f"/repos/{a.repo}/check-runs/{guard['check_id']}")
        runs = await gh.get(
            f"/repos/{a.repo}/commits/{pr['head']['sha']}/check-runs",
            params={"app_id": app.app_id, "per_page": 100},
        )
        problems = check_run_problems(cr, head_sha=pr["head"]["sha"], app_id=app.app_id)
        if cr.get("conclusion") != guard.get("conclusion"):
            problems.append(
                f"GitHub says {cr.get('conclusion')}, the run recorded {guard.get('conclusion')}"
            )
        seen = {
            "pr_head": pr["head"]["sha"],
            "check_run_head": cr.get("head_sha"),
            "conclusion": cr.get("conclusion"),
            "furnace_check_runs_on_head": runs.get("total_count"),
        }
        return problems, seen

    async def check_updates() -> tuple[list[str], dict[str, Any]]:
        if not guard.get("check_id"):
            raise NotRun("no Guard check run in the run record")
        cr = await gh.get(f"/repos/{a.repo}/check-runs/{guard['check_id']}")
        ann = await gh.get(f"/repos/{a.repo}/check-runs/{guard['check_id']}/annotations")
        out = cr.get("output") or {}
        problems = []
        if (
            not (cr.get("started_at") and cr.get("completed_at"))
            or cr["completed_at"] < cr["started_at"]
        ):
            problems.append("check run lacks a start and a later completion")
        if not out.get("title") or not out.get("summary"):
            problems.append("check run output has no title or summary")
        if cr.get("conclusion") == "failure" and not ann:  # Guard annotates the failing hunk
            problems.append("failed check run has no annotation on the changed prompt hunk")
        seen = {
            "started_at": cr.get("started_at"),
            "completed_at": cr.get("completed_at"),
            "title": out.get("title"),
            "annotations": [f"{x['path']}:{x['start_line']} {x['annotation_level']}" for x in ann][
                :5
            ],
        }
        return problems, seen

    async def draft_prs() -> tuple[list[str], dict[str, Any]]:
        if not forge_pr:
            raise NotRun("the run opened no Forge PR")
        problems, seen = [], {}
        r1 = await gh.get(f"/repos/{a.repo}/pulls/{r1_number}") if r1_number else None
        for num, base, built_on in (
            (forge_pr, "main", None),
            (
                repair_pr,
                r1["head"]["ref"] if r1 else "r1-request-id",
                r1["head"]["sha"] if r1 else None,
            ),
        ):
            if not num:
                seen["repair_pr"] = "none opened (repair not verified in the run)"
                continue
            pr = await gh.get(f"/repos/{a.repo}/pulls/{num}")
            commits = await gh.get(f"/repos/{a.repo}/pulls/{num}/commits", params={"per_page": 100})
            pr["_first_parent"] = (commits[0]["parents"] or [{}])[0].get("sha") if commits else None
            problems += check_draft_pr(pr, base_ref=base, built_on=built_on)
            seen[f"pr_{num}"] = {
                "draft": pr.get("draft"),
                "head": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "by": pr["user"]["login"],
                "url": pr["html_url"],
            }
        return problems, seen

    async def branches_intact() -> tuple[list[str], dict[str, Any]]:
        before = run.get("branches_before") or {}
        if not before:
            raise NotRun("the run did not record branch heads before it started")
        problems, seen = [], {}
        for br, sha in before.items():
            now = (await gh.get(f"/repos/{a.repo}/git/ref/heads/{br}"))["object"]["sha"]
            seen[br] = {"before": sha, "now": now}
            if now != sha:
                problems.append(f"{br} moved from {sha[:7]} to {now[:7]}")
        return problems, seen

    async def no_duplicates() -> tuple[list[str], dict[str, Any]]:
        prs = await gh.get(f"/repos/{a.repo}/pulls", params={"state": "open", "per_page": 100})
        ours = [p for p in prs if p["head"]["ref"].startswith("furnace/")]
        by_base: dict[str, list[int]] = {}
        for p in ours:
            by_base.setdefault(p["base"]["ref"], []).append(p["number"])
        problems = [
            f"{len(v)} open Furnace PRs into {k}: {v}" for k, v in by_base.items() if len(v) > 1
        ]
        rc = run.get("checks") or {}
        for k in ("forge_replay_same_pr", "repair_replay_same_pr"):
            if rc.get(k) is not True:
                problems.append(f"run check {k} = {rc.get(k)}")
        return problems, {"open_furnace_prs_by_base": by_base}

    for name, fn in (
        ("permissions", permissions),
        ("token_scope", token_scope),
        ("attribution", attribution),
        ("check_updates", check_updates),
        ("draft_prs", draft_prs),
        ("branches_intact", branches_intact),
        ("no_duplicates", no_duplicates),
    ):
        await check(name, fn)

    # ---------------------------------------------------------------- webhook receiver
    async def webhook_real_deliveries() -> tuple[list[str], dict[str, Any]]:
        if not a.api:
            raise NotRun(
                "no --api: start the API with the App's webhook secret and forward deliveries"
            )
        from furnace.db.models import WebhookDelivery
        from furnace.db.session import session_scope
        from sqlalchemy import select

        started = _utc(run["manifest"]["started_at"])
        repo_id = (await gh.get(f"/repos/{a.repo}"))["id"]
        dl = await jwt_gh.get("/app/hook/deliveries", params={"per_page": 100})
        mine = [
            d for d in dl
            if d.get("event") == "pull_request"
            and d.get("repository_id") == repo_id
            and not d.get("redelivery")
            and _utc(d.get("delivered_at")) >= started
        ]  # fmt: skip
        if not mine:
            raise NotRun("GitHub delivered no pull_request event since the run started")
        guids = sorted({d["guid"] for d in mine})
        async with session_scope() as s:
            rows = (
                (
                    await s.execute(
                        select(WebhookDelivery).where(WebhookDelivery.delivery_id.in_(guids))
                    )
                )
                .scalars()
                .all()
            )
        by = {r.delivery_id: r for r in rows}
        problems = [f"delivery {g} never reached the receiver" for g in guids if g not in by]
        problems += [
            f"delivery {g} recorded via {by[g].source}, not over HMAC (push)"
            for g in guids if g in by and by[g].source != "push"
        ]  # fmt: skip
        seen = {
            "deliveries": len(guids),
            "status_codes": sorted({d.get("status_code") for d in mine}),
            "outcomes": sorted({str(by[g].outcome) for g in guids if g in by}),
        }
        state["redeliver_id"] = mine[0]["id"]
        state["redeliver_guid"] = mine[0]["guid"]
        return problems, seen

    async def webhook_redelivery_noop() -> tuple[list[str], dict[str, Any]]:
        if "redeliver_id" not in state:
            raise NotRun("no real delivery to redeliver")
        from furnace.db.models import Job, WebhookDelivery
        from furnace.db.session import session_scope
        from sqlalchemy import func, select

        async def counts() -> tuple[int, int]:
            async with session_scope() as s:
                d = await s.scalar(
                    select(func.count())
                    .select_from(WebhookDelivery)
                    .where(WebhookDelivery.delivery_id == state["redeliver_guid"])
                )
                j = await s.scalar(
                    select(func.count()).select_from(Job).where(Job.kind == "guard.pr")
                )
            return int(d or 0), int(j or 0)

        before = await counts()
        r = await jwt_gh.c.post(f"/app/hook/deliveries/{state['redeliver_id']}/attempts")
        if r.status_code >= 300:
            return [f"redelivery request refused: {r.status_code} {r.text[:200]}"], {}
        await asyncio.sleep(a.redeliver_wait)
        dl = await jwt_gh.get("/app/hook/deliveries", params={"per_page": 50})
        again = [d for d in dl if d["guid"] == state["redeliver_guid"] and d.get("redelivery")]
        after = await counts()
        problems = []
        if not again:
            problems.append("GitHub shows no redelivery attempt yet (increase --redeliver-wait)")
        elif again[0].get("status_code") not in (200, 202):
            problems.append(
                f"the receiver answered the redelivery with {again[0].get('status_code')}"
            )
        if after != before:
            problems.append(f"rows changed on redelivery: deliveries/jobs {before} -> {after}")
        return problems, {
            "before": before,
            "after": after,
            "redelivery_status": [d.get("status_code") for d in again],
        }

    async def webhook_forgery_refused() -> tuple[list[str], dict[str, Any]]:
        if not a.api:
            raise NotRun("no --api")
        from furnace.settings import get_settings

        secret = get_settings().github_webhook_secret
        if secret is None:
            raise NotRun("FURNACE_GITHUB_WEBHOOK_SECRET is not set in this environment")
        url = a.api.rstrip("/") + "/api/github/webhook"
        body = json.dumps({"zen": "furnace verification ping", "hook_id": 0}).encode()
        guid = str(uuid.uuid4())
        hdr = {"content-type": "application/json", "X-GitHub-Event": "ping"}
        cases = {
            "unsigned": ({**hdr, "X-GitHub-Delivery": guid}, 401),
            "wrong secret": ({**hdr, "X-GitHub-Delivery": guid, "X-Hub-Signature-256": sign("not-the-secret", body)}, 401),
            "tampered body": ({**hdr, "X-GitHub-Delivery": guid, "X-Hub-Signature-256": sign(secret.get_secret_value(), body + b" ")}, 401),
            "valid": ({**hdr, "X-GitHub-Delivery": guid, "X-Hub-Signature-256": sign(secret.get_secret_value(), body)}, 202),
            "valid replay": ({**hdr, "X-GitHub-Delivery": guid, "X-Hub-Signature-256": sign(secret.get_secret_value(), body)}, 202),
        }  # fmt: skip
        problems, seen = [], {}
        async with httpx.AsyncClient(timeout=20) as c:
            for name, (h, want) in cases.items():
                r = await c.post(url, content=body, headers=h)
                seen[name] = r.status_code
                if r.status_code != want:
                    problems.append(f"{name}: HTTP {r.status_code}, expected {want}")
                if (
                    name == "valid replay"
                    and r.status_code == 202
                    and not r.json().get("duplicate")
                ):
                    problems.append("a replayed delivery GUID was not reported as a duplicate")
        return problems, seen

    state: dict[str, Any] = {}
    await check("webhook_real_deliveries", webhook_real_deliveries)
    await check("webhook_redelivery_noop", webhook_redelivery_noop)
    await check("webhook_forgery_refused", webhook_forgery_refused)
    await gh.aclose()
    await jwt_gh.aclose()

    ran = [r for r in results if r["ok"] is not None]
    core_skipped = [r["check"] for r in results if r["check"] in CORE and r["ok"] is None]
    verdict = (
        "PASS"
        if all(r["ok"] for r in ran) and not core_skipped
        else "FAIL: " + ", ".join(r["check"] for r in results if r["ok"] is False)
        if any(r["ok"] is False for r in results)
        else "INCOMPLETE: not run " + ", ".join(core_skipped)
    )
    return {"repo": a.repo, "run": str(a.run), "results": results, "verdict": verdict}


def _utc(ts: str | None) -> datetime:
    """ISO-8601 with 'Z' or an offset -> aware UTC datetime (epoch if missing)."""
    if not ts:
        return datetime.fromtimestamp(0, UTC)
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)


class NotRun(Exception):
    """The check's precondition is absent; recorded as 'not run', never as a pass."""


def render(res: dict[str, Any]) -> str:
    lines = [
        "# Live GitHub verification",
        "",
        f"Repository `{res['repo']}`; run record `{res['run']}`; verified "
        f"{res['manifest']['started_at']}. Result: **{res['verdict']}**.",
        "",
        "| check | result | problems | what GitHub / the receiver showed |",
        "|---|---|---|---|",
    ]
    for r in res["results"]:
        status = "not run" if r["ok"] is None else "ok" if r["ok"] else "**FAIL**"
        seen = json.dumps(r.get("seen") or {}, default=str)[:400].replace("|", "/")
        lines.append(f"| {r['check']} | {status} | {'; '.join(r['problems']) or '–'} | {seen} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--run", help="live_run.json (default: the newest *-live-github run)")
    p.add_argument("--api", help="local receiver base URL, e.g. http://localhost:8010")
    p.add_argument("--redeliver-wait", type=float, default=15.0)
    a = p.parse_args()
    if not a.run:
        runs = sorted((ROOT / "bench/results").glob("*-live-github/live_run.json"))
        if not runs:
            raise SystemExit("no live_run.json found: run scripts/live_github_run.py first")
        a.run = str(runs[-1])
    mf = manifest()
    run = json.loads(Path(a.run).read_text(encoding="utf-8"))
    res = {"manifest": mf, **asyncio.run(verify(a, run))}
    out = Path(a.run).parent
    write_json(out / "verify.json", res)
    (out / "verify.md").write_text(render(res), encoding="utf-8")
    print(render(res))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
