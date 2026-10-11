# Hosted control plane: Supabase + Render + Vercel (free tiers, about 30 minutes)

The hosted part serves the website, public GitHub scans (Blueprint) and the FurnaceBench
results. GPU work (benchmarks, sandboxed evals, Guard, repair) stays on the laptop runner.

```
browser ── Vercel (apps/web, Next.js) ──/api/*──► Render (apps/api, FastAPI + embedded scan worker) ──► Supabase Postgres
```

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

## 4. Verify (each was checked against the local image on 2026-10-10)

- Landing page loads: hero before/after, "lab offline · showing recorded run", FurnaceBench strip.
- Paste `https://github.com/peterw/llamav2-chat` into the scan box → live log → Blueprint
  (Replicate call, engine replicate). A renamed repo (`vercel/ai-chatbot`) still scans.
- `/lab`: "Lab GPU offline" button with the reason; `/guard/r1_dynamic_head`: "Runner offline";
  `/bench`: the corrections box above the 2026-10-06 report; `/evals`: labeling disabled.
- API: `curl https://furnace-api-XXXX.onrender.com/api/live/telemetry` prints `event: disabled`;
  `POST /api/public/scans` with `{"kind":"fixture",...}` is 404 (dev only).

## Updating results

FurnaceBench results are baked into the API image. After committing new `bench/results`,
push; Render redeploys and the site shows the new numbers.
