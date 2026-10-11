# GitHub App setup and the live run (about 10 minutes)

Furnace talks to GitHub only through a GitHub App. Every job mints a token scoped to one
repository and only the permissions that job needs; Furnace opens **draft** pull requests
and check runs, never merges, and never pushes to a default branch.

| what | permission | used by |
|---|---|---|
| read revisions (tarballs) | Contents: read | Scan, Forge, Guard, repair |
| commit to a new `furnace/*` branch | Contents: write | Forge and repair draft PRs only |
| read PRs, open draft PRs | Pull requests: read & write | Guard (read), Forge/repair (write) |
| report the check run | Checks: read & write | Guard |
| (mandatory) | Metadata: read | all |
| event | `pull_request` | Guard |

No account or organization permissions. Per job, the token is narrower still
(`SCAN_PERMISSIONS`, `GUARD_PERMISSIONS`, `PR_PERMISSIONS` in
`packages/furnace/src/furnace/github/client.py`).

## 1. Create the App from its manifest (2 clicks)

```bash
cd C:/dev/furnace
uv run furnace gh-setup --name furnace-dev-<your-username>
```

A browser tab opens on `http://127.0.0.1:8765/` showing the manifest (the table above) and
forwards it to GitHub. Review it and click **Create GitHub App**. GitHub redirects back to
`127.0.0.1` with a one-time code; Furnace exchanges it and writes:

- the private key to `~/.furnace/<app-slug>.pem` (outside the repository, owner-only),
- `FURNACE_GITHUB_APP_ID`, `FURNACE_GITHUB_PRIVATE_KEY_PATH`, `FURNACE_GITHUB_WEBHOOK_SECRET`
  into `.env` (git-ignored). Secrets are never printed.

It prints the install link. **Install** the App on **Only select repositories** →
`furnace-demo-f1` (do step 2 first if that repository does not exist yet).

Webhook URL: by default `gh-setup` points the App's webhook at a fresh smee.io channel.
Furnace does not read from smee; it only gives GitHub somewhere to deliver, so that the
App's delivery log fills, and `furnace gh-poll` (step 4) reads that log over the
authenticated GitHub API. The channel URL is unguessable but unauthenticated: anyone who
has it can read the payloads, which for a public demo repository are public data anyway.
With a deployed API, pass `--webhook-url https://<api>/api/github/webhook` instead.

Manual alternative: GitHub → Settings → Developer settings → GitHub Apps → New, with the
permissions in the table, then put the App id and the key path in `.env` as above.

Check it (prints the App name, its permissions and the installations):

```bash
uv run furnace gh-check
```

## 2. The demo repository

The local repository is prepared at `C:\dev\furnace-demo-f1` (made with
`scripts/demo_repo.py`): branch `main` = F1, branch `r1-request-id` = the exact R1 change
FurnaceBench measured (one file, `app/prompts.py`). On GitHub create an empty **public**
repository `furnace-demo-f1` (F1 contains no secrets; the landing-page scan without login
reads only public repositories), then:

```bash
cd C:/dev/furnace-demo-f1
git remote add origin https://github.com/<you>/furnace-demo-f1.git
git push -u origin main r1-request-id
```

## 3. The live run, command by command

Prerequisites: Docker Desktop; lab vLLM up
(`HF_HOME_HOST=... docker compose --profile gpu up -d vllm`); laptop on AC power.

```bash
cd C:/dev/furnace
Q=fixtures/apps/support-rag-py/docs/facts.json
S=fixtures/scenarios/f1_suite.py

# Forge: plan + sandbox-validate, then open a draft PR with the reliability layer
uv run furnace gh-forge <you>/furnace-demo-f1 --questions $Q \
    --workload bench/results/2026-10-04-f1-quality/workload-f1-traces-qwen05b.yaml --open-pr

# The regression PR: on GitHub open a PR from r1-request-id into main,
# title "Add request id and timestamp to the system prompt for debugging"; note its number N

# Guard: targeted checks -> a check run on the PR (expect a failure with the perf table)
uv run furnace gh-guard <you>/furnace-demo-f1 N --suite $S --questions $Q --max-prompt-tokens 3840

# Repair: regression test first, sandbox validation, perf gate -> draft PR into the PR branch
uv run furnace gh-repair <you>/furnace-demo-f1 N --suite $S --questions $Q --open-pr
```

Without `--open-pr`, Forge and repair are dry runs that print what they would change.
Re-running Forge or repair on the same commit returns the draft PR the first run opened
(also if a human closed it); it never opens a second one. `gh-guard` runs again when
called by hand; `--reuse` returns the completed check run on that commit instead.

## 4. Event-driven: Guard (and repair) on every PR push

```
# .env on the laptop, in addition to step 1
FURNACE_GUARD_SUITE_PATH=C:/dev/furnace/fixtures/scenarios/f1_suite.py
FURNACE_GUARD_QUESTIONS_PATH=C:/dev/furnace/fixtures/apps/support-rag-py/docs/facts.json
FURNACE_GUARD_MAX_PROMPT_TOKENS=3840
FURNACE_GITHUB_ALLOWED_REPOS=<you>/furnace-demo-f1     # optional, recommended
FURNACE_GUARD_AUTO_REPAIR=true                         # optional: the write consent for repair PRs
```

Two terminals: `uv run poe runner` (claims jobs) and `uv run poe gh-poll` (reads the
delivery log every 10 s). Opening or pushing to a non-draft PR from the same repository
then: delivery recorded once → one `guard.pr` job per head commit → check run. If the check
fails with a regression signature the repair loop supports (today: prefix instability)
and auto-repair is on, one `repair.pr` job per head commit follows and, only if a
candidate passes the regression test, the existing tests and the perf gate, opens a draft
PR into the PR's branch. Every delivery and its outcome is a row in `webhook_deliveries`;
every job's stages are `job_events`.

With a deployed API instead (docs/deploy.md): App webhook URL
`https://<api>/api/github/webhook` with the secret from `.env` set on the API as
`FURNACE_GITHUB_WEBHOOK_SECRET`, and the runner's `FURNACE_DATABASE_URL` pointing at the
same database. The API verifies the HMAC signature and only enqueues; it never runs
repository code. Push and poll can run together: the delivery GUID dedupes them.

## Guarantees and their tests

| guarantee | test |
|---|---|
| a delivery GUID is processed once (redeliveries, replays) | `apps/api/tests/test_github_webhook.py::test_a_replayed_delivery_is_a_no_op` |
| one active Guard job per PR head commit | `test_two_events_for_the_same_head_commit_share_one_job` |
| malformed or oversized signed payloads: rejected, nothing written | `test_malformed_signed_events_are_rejected_without_side_effects` |
| no second PR on retry; a closed PR is not reopened; a crash between branch and PR resumes | `packages/furnace/tests/test_github.py` |
| check run reused per head commit, closed on cancellation | `packages/furnace/tests/test_github_flows.py` |
| no action under a different installation than the event's | `test_guard_pr_refuses_to_act_under_another_installation` |
| a stale worker cannot overwrite the job's outcome; a lost lease cancels the run | `packages/furnace/tests/test_jobs_queue.py` |
| repair only with consent, once per head commit | `packages/furnace/tests/test_github_jobs.py` |
| delivery-log poller: new deliveries once, no old history | `packages/furnace/tests/test_github_setup.py` |

All of these run against a mock GitHub. The first run against the real API remains the
open item in the README status table until it has been done and recorded.

## Notes

- PRs from forks are refused: their code would run in the sandbox.
- The suite file (`fixtures/scenarios/f1_suite.py`) binds F1's checks to graph nodes; for
  another repository, write a suite file with the same `SuiteItem` shape.
