# Hosted control plane: Supabase + Render + Vercel (free tiers, about 30 minutes)

The hosted part serves the website, public GitHub scans (Blueprint) and the FurnaceBench
results. GPU work (benchmarks, sandboxed evals, Guard, repair) stays on the laptop runner.

```
browser ── Vercel (apps/web, Next.js) ──/api/*──► Render (apps/api, FastAPI + embedded scan worker) ──► Supabase Postgres
```

## Recorded-only site: Cloudflare Pages Free ($0, static export)

Hosting budget: **$0**. No paid plan, trial, payment method, purchased domain, paid storage or
paid Workers plan. The site is plain static files on the free `*.pages.dev` address.


The landing page, `/demo` (with the screen recording), `/bench` and every other evidence page
need no API, database or runner: with `NEXT_PUBLIC_RECORDED_ONLY=true` the web app is a static
export (`apps/web/out/`) that answers the read-only `/api/bench/*` routes at build time from `apps/web/lib/bench-snapshot.json` (written by
`scripts/export_bench_snapshot.py` from the API's own route functions; a test fails if it is
stale) and the Inference Lab reads `apps/web/public/recorded/live-recorded.json`. Nothing under
`/api` is routed, so no visitor can start anything; live controls say they are unavailable
(Guard "Live runs off here", Lab "no lab on this site", pilot status "NOT HERE", scan form
replaced by a notice, labeling queue disabled). Render and Supabase are needed only for hosted
functionality: public scans, a webhook receiver with a public URL, live status.

### Why Cloudflare Pages Free (terms checked 2026-10-14)

- Plan limits (<https://developers.cloudflare.com/pages/platform/limits/>): 25 MiB per file,
  20,000 files per site, 500 builds a month, 2,000 static redirects; no bandwidth or request
  cap is listed for static assets. This export: 193 files, about 23 MB; the largest file is the
  WebM recording at 12.95 MiB (the MP4 is 3.28 MiB). No Pages Functions are used, so nothing
  counts against the Workers quota.
- Commercial use: Cloudflare's terms do not limit free plans to personal or non-commercial use
  (unlike Vercel Hobby, whose fair-use guidelines do).
- Video: the general CDN terms require serving "video and other large files" through Paid
  Services "(e.g., the Developer Platform, Images, and Stream)"; Pages is part of the Developer
  Platform, whose terms add no video restriction. Two short silent recordings (17 MB together)
  are served from Pages assets. If Cloudflare ever objects, drop the WebM (the MP4 plays
  everywhere) or link the recording elsewhere; nothing else depends on it.

### Static export: what changed for it

- `next.config.ts`: recorded-only builds use `output: "export"` and unoptimized images (the app
  uses no `next/image`); no rewrites. Live builds are unchanged and still render per request
  (`lib/render.ts`, `connection()` only when not recorded-only).
- Dynamic routes: `/guard/[scenario]` is generated for every recorded scenario; `/scans/[id]`
  only exists behind the API, so the export generates one placeholder that renders the 404 page.
- `/bench?c=...`: a static page has no query string at build time; it shows the newest report
  and the other campaigns link to their committed `REPORT.md` on GitHub.
- Redirects: `public/_redirects` gives `/pricing` → `/pilot#terms-h` (302) on Cloudflare; the
  page also redirects in the browser on any other static host.
- 404: the export's `404.html` is served by Pages with status 404 for unknown paths, `/api/*`
  and `/healthz`.
- `scripts/export-segment-aliases.mjs` (run by `pnpm build:static`): Next.js 16 writes
  per-segment prefetch files nested but its client router requests them dot-joined; without the
  aliases every link logs a 404 and falls back to a full page load.

### Deployed

**https://furnace-5h6.pages.dev**, commit 08868cf, 2026-10-15
(`bench/results/2026-10-15-hosted/`): smoke test 18 of 20, browser pass clean on desktop and
phone-sized Chromium. Open limitation: Pages answers `Range` requests for the recordings with
200 (full file), and Safari needs 206 for media, so the recording may not play on iPhones or
in Safari.

Notes from the first deployment:
- Wrangler 4.151's `pages project create` now hands off to a Workers flow that auto-detects
  Next.js and wants its own build; do not use it. Create the classic project with the API
  (`POST /accounts/<id>/pages/projects` with `{"name": "furnace", "production_branch": "main"}`),
  then `wrangler pages deploy out`.
- `wrangler login --device --scopes account:read user:read pages:write` worked; the default
  localhost-callback login timed out twice on this laptop.
- Cloudflare answers 403 to Python's default `Python-urllib` User-Agent; the smoke test sends its own.

### Build, check locally, deploy

```bash
cd apps/web
NEXT_PUBLIC_RECORDED_ONLY=true pnpm build:static          # -> out/
npx wrangler@4.151.0 pages dev out --port 8788             # Cloudflare's routing, locally
uv run python scripts/smoke_hosted.py --web http://127.0.0.1:8788   # from the repo root
npx wrangler@4.151.0 login --device --scopes account:read user:read pages:write   # owner approves
# project: created once through the API (see "Deployed" above), not `pages project create`
npx wrangler@4.151.0 pages deploy out --project-name furnace --branch main --commit-hash "$(git rev-parse HEAD)" --commit-message "recorded-only site"
```

Then, with the laptop's API, runner and vLLM stopped, run the smoke test against
`https://<project>.pages.dev` (`--out bench/results/<date>-hosted/smoke-web.md`) and open it in a
private window on a desktop and a phone. `wrangler pages dev` does not answer byte-range
requests (it returns 200), so the recording's 206 check is only meaningful on the real edge.
Contact link: the LinkedIn default (`NEXT_PUBLIC_CONTACT_URL` unset).

When results change, run `uv run python scripts/export_bench_snapshot.py`, commit, rebuild and
redeploy.

### Vercel (not used: $0 budget)

Vercel Hobby is limited to non-commercial personal use
(<https://vercel.com/docs/limits/fair-use-guidelines>) and Pro is paid ($20/month); neither is
used. The same static `out/` would deploy there unchanged if that ever changes.

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
