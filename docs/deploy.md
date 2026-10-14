# Hosted control plane: Supabase + Render + Vercel (free tiers, about 30 minutes)

The hosted part serves the website, public GitHub scans (Blueprint) and the FurnaceBench
results. GPU work (benchmarks, sandboxed evals, Guard, repair) stays on the laptop runner.

```
browser ── Vercel (apps/web, Next.js) ──/api/*──► Render (apps/api, FastAPI + embedded scan worker) ──► Supabase Postgres
```

## Recorded-only site: Vercel alone (the first launch, about 10 minutes)

The landing page, `/demo` (with the screen recording), `/bench` and every other evidence page
need no API, database or runner: with `NEXT_PUBLIC_RECORDED_ONLY=true` the web app answers the
read-only `/api/bench/*` routes from `apps/web/lib/bench-snapshot.json` (written by
`scripts/export_bench_snapshot.py` from the API's own route functions; a test fails if it is
stale) and the Inference Lab reads `apps/web/public/recorded/live-recorded.json`. Nothing under
`/api` is routed, so no visitor can start anything; live controls say they are unavailable
(Guard "Live runs off here", Lab "no lab on this site", pilot status "NOT HERE", scan form
replaced by a notice, labeling queue disabled). Render and Supabase are needed only for hosted
functionality: public scans, a webhook receiver with a public URL, live status.

1. vercel.com → sign up with GitHub (Hobby, free) → Add New → Project → import
   `dilipna/Furnace4LLM` (grant Vercel access to that repository only).
2. **Root Directory: `apps/web`**; framework Next.js and pnpm are detected.
3. Environment variables (Production): `NEXT_PUBLIC_RECORDED_ONLY` = `true`; optionally
   `NEXT_PUBLIC_CONTACT_URL` = your `mailto:` or LinkedIn URL (default: the LinkedIn profile).
   Do **not** set `FURNACE_API_URL`. Both are read at build time: change them, then redeploy.
4. Deploy, then verify from any machine (laptop runner and local API may be off):

```bash
uv run python scripts/smoke_hosted.py --web https://<project>.vercel.app     [--contact <NEXT_PUBLIC_CONTACT_URL>] --out bench/results/<date>-hosted/smoke-web.md
```

It checks every page for its recorded content and recorded-only notices, `/pricing` → `/pilot`,
the contact link, both recordings (WebM and the H.264 MP4 fallback) answering range requests,
the poster and recorded telemetry, that `/api/*` and `/healthz` answer 404, and a 404 page.
Last local run (recorded build, API and runner stopped): 2026-10-14, all 20 checks passed.

When results change, run `uv run python scripts/export_bench_snapshot.py`, commit, push:
Vercel redeploys from `main`.

## 0. Repository and a local smoke test of the image

The repository is already on GitHub (`github.com/dilipna/Furnace4LLM`, public); `.env`, keys
and `bench/.cache` are git-ignored, and CI (`.github/workflows/ci.yml`) runs on every push.

Before the first Render deploy, build and run the exact image locally (verified on 2026-10-10;
this is how a missing-README build failure was caught before Render saw it):

```bash
docker compose up -d postgres
docker exec furnace-postgres-1 psql -U furnace -d postgres -c "create database furnace_deploytest;"
docker build -f apps/api/Dockerfile -t furnace-api:deploytest .
docker run -d --name furnace-deploytest --add-host=host.docker.internal:host-gateway \
  -e FURNACE_ENV=prod -e PORT=8020 -p 8020:8020 \
  -e FURNACE_DATABASE_URL=postgresql+asyncpg://furnace:furnace@host.docker.internal:5433/furnace_deploytest \
  -e FURNACE_MASTER_KEY=$(python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())") \
  -e FURNACE_SESSION_SECRET=some-long-random-string -e FURNACE_WEB_ORIGIN=http://localhost:3200 \
  furnace-api:deploytest
curl localhost:8020/healthz                      # {"ok":true,...,"db":true}: migrations ran
cd apps/web && FURNACE_API_URL=http://localhost:8020 pnpm build && pnpm exec next start --port 3200
```

Then open http://localhost:3200: it is what visitors will see (recorded lab run, "Lab GPU
offline", "Runner offline", corrections on /bench). Remove with `docker rm -f furnace-deploytest`.

### Local production-mode check, 2026-10-14 (commit 5806c30)

Image built from the committed tree (`git archive HEAD | docker build -f apps/api/Dockerfile -`),
run with `FURNACE_ENV=prod` against an empty database:

| probe | result |
|---|---|
| `GET /healthz` | `{"ok":true,"db":true}`: migrations ran on start |
| `GET /api/runners` | ids `runner-N`, capabilities limited to gpu/docker (no hostname, OS build or driver) |
| `GET /api/live/telemetry` | `event: disabled` |
| `GET /api/bench/campaigns` | baked-in results, including `gate_validation` and `set6_findings` |
| `POST /api/public/scans` kind `fixture` | 404 (dev only) |
| `POST /api/labels` | 403 "labeling is disabled on this deployment" |
| `POST /api/github/webhook` without a configured secret | 503 "webhooks are not configured" |
| `POST /api/public/scans` kind `github` (`peterw/llamav2-chat`) | 201, scan succeeded through the embedded worker |

Not checked here: the Vercel build against this API (same web code as the local production
build), Supabase's pooler, Render's sleep behavior. Nothing is deployed.

## 1. Supabase (database)

1. supabase.com → New project (free). Pick a strong database password; region near you.
2. Project → **Connect** → **Session pooler** → copy the URI. (Render's free tier has no IPv6,
   and the direct connection is IPv6-only; the session pooler is IPv4 and supports the
   prepared statements asyncpg uses. Do not use the transaction pooler on port 6543.)
3. Change the scheme for SQLAlchemy's async driver:
   `postgresql://postgres.xxxx:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres`
   → `postgresql+asyncpg://postgres.xxxx:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres`

Migrations run automatically when the API container starts.

## 2. Render (API)

1. render.com → New → **Blueprint** → connect the `furnace` repository. Render reads
   `render.yaml` and proposes the `furnace-api` web service (Docker, free plan).
2. Fill in the secret environment variables it asks for:

| variable | value |
|---|---|
| `FURNACE_DATABASE_URL` | the `postgresql+asyncpg://` URI from step 1 |
| `FURNACE_MASTER_KEY` | output of `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"` |
| `FURNACE_SESSION_SECRET` | any long random string |
| `FURNACE_WEB_ORIGIN` | your Vercel URL from step 3 (can be set after step 3) |

3. Deploy. Check `https://furnace-api-XXXX.onrender.com/healthz` returns `{"ok": true, ...}`.

With `FURNACE_ENV=prod` the API refuses to start with development secrets, and labeling is
read-only (`FURNACE_LABELS_WRITABLE=false`, set in the image). The hosted API has no lab
endpoint, so live lab telemetry and "Run it now" are off (`FURNACE_LIVE_LAB=false`, set in the
image): the panels show the recorded RQ4 run, labeled, and Guard runs need the laptop runner. The free service sleeps after
15 minutes idle; the first request after that takes about a minute.

## 3. Vercel (web)

1. vercel.com → Add New → Project → import the `furnace` repository.
2. **Root Directory: `apps/web`** (framework Next.js is detected; pnpm from the lockfile).
3. Environment variable: `FURNACE_API_URL` = `https://furnace-api-XXXX.onrender.com`. Set it
   **before** the first build: the `/api/*` rewrite target is fixed when Next.js builds, so a
   later change needs a redeploy.
4. Deploy. The browser only talks to the Vercel origin; `/api/*` is rewritten to Render
   (`apps/web/next.config.ts`), so no CORS configuration is needed.

## 4. Verify (one command)

```bash
uv run python scripts/smoke_hosted.py --api https://furnace-api-XXXX.onrender.com     --web https://furnace-XXXX.vercel.app --scan github.com/peterw/llamav2-chat     --out bench/results/<date>-hosted/smoke.md
```

It waits up to two minutes for a sleeping API, then checks: health and database; runner list
without host details; live lab and visitor runs off; refusals (Guard run 403, fixture scan 404,
labels 403); recorded results present; the web pages (`/`, `/pilot`, `/guard/r1_dynamic_head`,
`/bench`) and the `/api` rewrite; one public scan end to end. Exit 0 only if every check
passed. Commit the `--out` file; only then say "deployed and verified". Last run: against the
production image locally, 2026-10-14 at 0b776b5, all checks passed (no hosted run yet).

## Environment variables, complete

Secrets go only into the Render dashboard or the runner's `.env` (git-ignored). The web app
has **no secrets**: every `NEXT_PUBLIC_*` value is visible to anyone.

| service | variable | value | secret |
|---|---|---|---|
| API (Render) | `FURNACE_ENV` | `prod` (refuses dev secrets and writable labels) | no |
| | `FURNACE_DATABASE_URL` | Supabase session-pooler URI, `postgresql+asyncpg://` | **yes** |
| | `FURNACE_MASTER_KEY` | 32 random bytes, base64 | **yes** |
| | `FURNACE_SESSION_SECRET` | long random string | **yes** |
| | `FURNACE_WEB_ORIGIN` | the Vercel URL | no |
| | `FURNACE_GITHUB_WEBHOOK_SECRET` | only if GitHub delivers webhooks to this API | **yes** |
| | `FURNACE_GITHUB_ALLOWED_REPOS` | e.g. `dilipna/furnace-demo-f1` | no |
| | set in the image | `FURNACE_LIVE_LAB=false`, `FURNACE_PUBLIC_RUNS=false`, `FURNACE_LABELS_WRITABLE=false`, `FURNACE_EMBEDDED_WORKER=true`, `FURNACE_BENCH_DIR=/app/bench` | no |
| Web (Vercel) | `FURNACE_API_URL` | the Render URL; server-side only, fixed at build | no |
| | `NEXT_PUBLIC_CONTACT_URL` | where "Ask about a pilot" goes (default: LinkedIn) | no, public |
| | `NEXT_PUBLIC_DEMO_VIDEO` | optional; default `/demo/furnace-demo.webm`, shipped with the site | no, public |
| Runner (your GPU machine) | `FURNACE_DATABASE_URL` | the same Supabase URI as the API | **yes** |
| | `FURNACE_GITHUB_APP_ID`, `FURNACE_GITHUB_PRIVATE_KEY_PATH`, `FURNACE_GITHUB_WEBHOOK_SECRET` | written by `furnace gh-setup`; the key file is in `~/.furnace/` | **yes** (key, secret) |
| | `FURNACE_GUARD_SUITE_PATH`, `FURNACE_GUARD_QUESTIONS_PATH`, `FURNACE_GUARD_MAX_PROMPT_TOKENS` | Guard's configuration (`docs/pilot.md`) | no |
| | `FURNACE_LAB_BASE_URL`, `FURNACE_LAB_MODEL` | the model endpoint to measure (default `http://localhost:8100/v1`, `lab`) | no |
| | `FURNACE_GUARD_AUTO_REPAIR` | `true` only with the owner's consent to draft repair PRs | no |

## The runner (stays on your machine)

Requirements: Docker (the sandbox), an NVIDIA GPU with the vLLM container
(`docker compose --profile gpu up -d vllm`), on AC power (benchmarks refuse to run on
battery), outbound access to GitHub and to the database. Start: `uv run poe runner`. It
registers in `runners`, heartbeats, and claims `runner`-queue jobs; the hosted API only
enqueues. With `FURNACE_PUBLIC_RUNS=false` on the API, visitors cannot start runs on it;
only GitHub events (and the owner's CLI) create work for it.

## GitHub webhooks to the hosted API

Point the App's webhook at `https://<api>/api/github/webhook` (GitHub → the App's settings →
Webhook URL), set `FURNACE_GITHUB_WEBHOOK_SECRET` on Render to the value in the runner's
`.env`, and redeploy. Without it the endpoint answers 503 and the runner can still read
events with `uv run poe gh-poll` (no public URL needed).

## Updating results

FurnaceBench results are baked into the API image. After committing new `bench/results`,
push; Render redeploys and the site shows the new numbers.
