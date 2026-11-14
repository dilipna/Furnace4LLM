# Targeted demo validation plan — NOT EXECUTED

Scope: only `dilipna/furnace-demo-f1`, one existing same-repository R1 PR and its exact head.
This plan needs separate authorization for real GitHub checks/draft proposals and local
inference load. It does not authorize a merge, deployment or a historical benchmark rerun.

Prerequisites: the new branch plus PR #5, a reviewed App installed on the demo only,
private key outside the checkout, Docker, dedicated Postgres database, trusted F1 suite and
questions, and the existing vLLM lab on AC power with no competing load. Confirm endpoint
and model with `/v1/models`; do not expose credentials in commands or captured output.
Use the existing cached model/image, not a new paid API. A structural-only run needs no GPU.

Before any write:

```powershell
uv run furnace gh-check
gh pr list --repo dilipna/furnace-demo-f1 --state open --json number,headRefName,headRefOid
$env:FURNACE_GITHUB_ALLOWED_REPOS = 'dilipna/furnace-demo-f1'
$env:FURNACE_GUARD_AUTO_REPAIR = 'false'
$env:FURNACE_GUARD_SUITE_PATH = (Resolve-Path fixtures/scenarios/f1_suite.py).Path
$env:FURNACE_GUARD_QUESTIONS_PATH = (Resolve-Path fixtures/apps/support-rag-py/docs/facts.json).Path
```

Set `DEMO_PR` and `DEMO_HEAD` to the chosen R1 PR and its current 40-hex head; recheck
before each case. Provision a **dedicated** `furnace_reliability_demo` database using the
existing Postgres instance and point `FURNACE_DATABASE_URL` there. Run `uv run poe migrate`.
Do not truncate the development database. No API/runner/poller may point at this validation
database concurrently; this avoids another worker consuming the probe jobs.

## Guard failure, retry, reuse and exhaustion

Save the following as an operator-owned `work/live_guard_probe.py`, review it, then run it
with `uv run python work/live_guard_probe.py`. It intentionally writes demo GitHub checks.
It uses the real worker, backoff and queue; the only injected fault is a bounded exception
before revision download. It creates unique sanitized question variants to isolate each
case from old completed evaluations; each retry/reuse within a case keeps identical inputs.

```python
import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from furnace import cli
from furnace.db.models import Job
from furnace.db.session import session_scope
from furnace.github import flows
from furnace.github import jobs as gh_jobs  # registers guard.pr
from furnace.jobs import queue, worker
from furnace.settings import get_settings
from sqlalchemy import select

REPO = "dilipna/furnace-demo-f1"
PR, HEAD = int(os.environ["DEMO_PR"]), os.environ["DEMO_HEAD"]


async def main():
    s = get_settings()
    assert s.database_url.rsplit("/", 1)[-1] == "furnace_reliability_demo"
    assert s.github_allowed_repos == REPO and not s.guard_auto_repair
    assert len(HEAD) == 40 and s.guard_suite_path and s.guard_questions_path
    app, suite, questions = gh_jobs._runner_config()
    inst = await app.installation_for(REPO)
    original_fetch = flows.fetch_revision

    async def read(job_id):
        async with session_scope() as db:
            j = await db.get(Job, job_id)
            assert j is not None
            return j.status, j.attempts, j.result, j.error

    async def enqueue():
        async with session_scope() as db:
            active = (
                await db.execute(select(Job).where(Job.status.in_(["queued", "running"])))
            ).first()
            assert active is None, "dedicated database must have no active jobs"
            j = await queue.enqueue(
                db,
                queue="runner",
                kind="guard.pr",
                max_attempts=2,
                payload={"repo": REPO, "number": PR, "head_sha": HEAD, "installation_id": inst},
            )
            j.timeout_s = 1800
            return j.id

    with tempfile.TemporaryDirectory() as td:
        qpath = Path(td) / "questions.json"

        def identity(label):
            qpath.write_text(json.dumps([q + " [demo " + label + "]" for q in questions]))
            os.environ["FURNACE_GUARD_QUESTIONS_PATH"] = str(qpath)
            get_settings.cache_clear()

        for mode in ["recover", "persistent"]:
            identity(mode + uuid.uuid4().hex)
            calls = 0

            async def fetch(*args):
                nonlocal calls
                calls += 1
                if mode == "persistent" or calls == 1:
                    raise RuntimeError("bounded demo-only revision-fetch fault")
                return await original_fetch(*args)

            job_id = await enqueue()
            with patch.object(flows, "fetch_revision", fetch):
                assert await worker.run_one("demo-probe", ["runner"])
                state = await read(job_id)
                assert state[0:2] == ("queued", 1) and state[2] is None
                await asyncio.sleep(6)  # honor the real first-retry backoff
                assert await worker.run_one("demo-probe", ["runner"])
                state = await read(job_id)
                assert state[1] == 2
                assert state[0] == ("succeeded" if mode == "recover" else "failed")
                assert not await worker.run_one("demo-probe", ["runner"])
                if mode == "recover":
                    assert state[2] and state[2]["conclusion"] != "skipped" and calls >= 3
                    before = calls
                    reused_id = await enqueue()
                    assert await worker.run_one("demo-probe", ["runner"])
                    reused = await read(reused_id)
                    assert reused[2] and reused[2].get("reused") and calls == before
                    assert reused[2]["check_id"] == state[2]["check_id"]
                    identity("changed-" + uuid.uuid4().hex)
                    changed_id = await enqueue()
                    assert await worker.run_one("demo-probe", ["runner"])
                    changed = await read(changed_id)
                    assert changed[0] == "succeeded" and changed[2] and not changed[2].get("reused")
                    assert calls > before
                    assert changed[2]["check_id"] != state[2]["check_id"]
                else:
                    assert state[2] is None and calls == 2
            print(
                json.dumps(
                    {
                        "case": mode,
                        "job_id": str(job_id),
                        "status": state[0],
                        "attempts": state[1],
                        "fetch_calls": calls,
                    }
                )
            )


asyncio.run(main())
```

Record check IDs and URLs from the job results/events plus the exact PR head. A succeeded
job alone is insufficient: recovery must have actual fetch/check events; reuse must have
the same check ID and no additional fetch; the changed identity must have a new check ID.
If the PR moved, stop and choose a new pinned head rather than accepting a superseded result.
Abort if the endpoint, sandbox or App is unavailable; do not weaken the gate to complete a demo.

## Repair contract on the same pinned demo head

Run these using a small operator script that loads `cli._app()`, `cli._suite(...)`, and
`cli._questions(...)`, then calls `asyncio.run(flows.repair_pr(...))` with:
`full_name=REPO`, `number=PR`, the reviewed suite/questions,
`expected_head_sha=HEAD`, `expected_installation=inst`, and `open_pr=True`.
Review the repository constant and expected head before executing.

1. **Offline proposal:** pass `target=None`. Assert `status == 'functional_only'`,
   `verification == {'functional': 'passed', 'performance': 'unverified'}` and a draft URL.
   Inspect the real PR using `gh pr view <URL> --json title,body,isDraft`: title must include
   `UNVERIFIED`, body must say performance unverified/not measured, and it must be a draft.
2. **Required evidence absent:** pass `target=cli._target(False)` while temporarily wrapping
   only this demo invocation with `patch.object(flows, 'run_gate', lambda *a, **k: {})` and
   `patch.object(flows, 'repair_perf_check', lambda *a: {})`. Real sandbox tests still run;
   no inference runs. Assert `status == 'rejected'`, `pr is None`; inspect demo branches/PRs
   before and after to confirm no proposal was created. Remove both patches immediately.
3. **Measured repair:** no wrappers, real target. Assert `verified` only if the current
   evidence validator accepts all three comparisons and the existing faster-than-head /
   bounded-vs-base rule passes. Otherwise record rejection/inconclusive honestly. Inspect
   the actual draft, interval evidence, failed-on-head/passed-on-base reproduction and
   candidate tests. No guaranteed passing outcome is implied.

Use the [pilot evidence record](evidence-template.md) for time, manual steps, IDs, exact
SHAs, error states and decision impact. Keep offline, fault-injected and measured cases
separate. These are targeted workflow checks, not a rerun of the historical GPU campaign.

Afterward stop only the dedicated probe, retain agreed evidence, close/delete only
explicitly authorized demo artifacts, and remove the dedicated database only with its
owner's consent. Do not merge or change the model/server's acceptance settings.
