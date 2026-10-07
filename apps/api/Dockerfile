# Furnace API (control plane) image. Build context: repository root.
#   docker build -f apps/api/Dockerfile -t furnace-api .
# Runs migrations, then serves on $PORT (Render sets it; default 8010). The embedded worker
# handles the cpu queue (scans) in-process; GPU/sandbox jobs belong to the laptop runner.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /app

# Dependency layer first (cached unless the lockfile or project metadata change).
COPY pyproject.toml uv.lock ./
COPY packages/inference/pyproject.toml packages/inference/pyproject.toml
COPY packages/furnace/pyproject.toml packages/furnace/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/inference/src packages/inference/src
COPY packages/furnace/src packages/furnace/src
COPY apps/api/furnace_api apps/api/furnace_api
RUN uv sync --frozen --no-dev --package furnace-api

# Read-only FurnaceBench results served by /api/bench (fixture scans are dev-only).
COPY bench/results bench/results
COPY bench/labels bench/labels
COPY bench/ground_truth bench/ground_truth

RUN useradd --create-home --uid 10001 furnace && mkdir -p /app/.data && chown -R furnace /app/.data
USER furnace

ENV FURNACE_BENCH_DIR=/app/bench FURNACE_EMBEDDED_WORKER=true FURNACE_LABELS_WRITABLE=false
EXPOSE 8010
CMD ["sh", "-c", "uv run --no-sync alembic -c packages/furnace/src/furnace/db/alembic.ini upgrade head && uv run --no-sync uvicorn furnace_api.main:app --host 0.0.0.0 --port ${PORT:-8010} --proxy-headers"]
