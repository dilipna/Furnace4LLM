# Hosted control plane: Supabase + Render + Vercel (free tiers, about 30 minutes)

The hosted part serves the website, public GitHub scans (Blueprint) and the FurnaceBench
results. GPU work (benchmarks, sandboxed evals, Guard, repair) stays on the laptop runner.

```
browser ── Vercel (apps/web, Next.js) ──/api/*──► Render (apps/api, FastAPI + embedded scan worker) ──► Supabase Postgres
```

## 0. Push the repository to GitHub (private)

```bash
cd C:/dev/furnace
git remote add origin https://github.com/<you>/furnace.git
git push -u origin main
```

`.env`, keys and `bench/.cache` are git-ignored. CI (`.github/workflows/ci.yml`) runs on push.

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
read-only (`FURNACE_LABELS_WRITABLE=false`, set in the image). The free service sleeps after
15 minutes idle; the first request after that takes about a minute.

## 3. Vercel (web)

1. vercel.com → Add New → Project → import the `furnace` repository.
2. **Root Directory: `apps/web`** (framework Next.js is detected; pnpm from the lockfile).
3. Environment variable: `FURNACE_API_URL` = `https://furnace-api-XXXX.onrender.com`.
4. Deploy. The browser only talks to the Vercel origin; `/api/*` is rewritten to Render
   (`apps/web/next.config.ts`), so no CORS configuration is needed.

## 4. Verify

- Landing page loads and shows the FurnaceBench strip (numbers from `bench/results`).
- Paste `https://github.com/streamlit/llm-examples` into the scan box → live log → Blueprint.
- `/lab`, `/guard`, `/bench`, `/evals` render (labeling buttons say labeling is disabled).

## Updating results

FurnaceBench results are baked into the API image. After committing new `bench/results`,
push; Render redeploys and the site shows the new numbers.
