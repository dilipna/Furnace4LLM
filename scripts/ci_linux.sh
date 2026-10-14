#!/usr/bin/env bash
# Run the CI jobs of .github/workflows/ci.yml in Linux containers, on the committed tree,
# before pushing. Catches what Windows runs miss (2026-10-12: a sandbox file mode that only
# failed on Linux reached main because nothing ran on Linux before the push).
#
#   bash scripts/ci_linux.sh            # python job (lint, types, migrations, tests) + web + image
#   bash scripts/ci_linux.sh python     # one job: python | web | image
#
# Faithful to the GitHub runner where it matters: Linux, Python 3.12 via uv, Postgres 17,
# a NON-root user (uid 1001, like the runner) that reaches Docker through the socket's group,
# and HEAD exactly as committed (git archive), so uncommitted files cannot make it pass.
# The sandbox tests bind-mount temp directories, so the python job's work tree lives at a path
# inside the Docker VM that the job container and the daemon both see (the VM's /tmp, a small
# tmpfs: a killed run's leftovers are removed by `docker run --rm -v /tmp:/t alpine rm -rf
# /t/furnace-ci-*`).
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows would rewrite /var/run/docker.sock and /tmp paths

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
JOBS=${*:-python web image}
TAG=furnace-ci-$$
VMDIR=/tmp/$TAG
SHA=$(git rev-parse --short HEAD)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "note: uncommitted changes are NOT tested; this checks HEAD $SHA as committed" >&2
fi

cleanup() {
  docker rm -f "$TAG-pg" >/dev/null 2>&1 || true
  docker network rm "$TAG" >/dev/null 2>&1 || true
  docker run --rm -v /tmp:/vmtmp alpine rm -rf "/vmtmp/$TAG" >/dev/null 2>&1 || true
}
trap cleanup EXIT

stage_tree() {
  git archive HEAD | docker run --rm -i -v "$VMDIR:$VMDIR" alpine \
    sh -c "mkdir -p $VMDIR/src $VMDIR/tmp && tar -x -C $VMDIR/src && chown -R 1001:1001 $VMDIR"
}

run_python() {
  echo "== python job at $SHA"
  docker network create "$TAG" >/dev/null
  docker run -d --name "$TAG-pg" --network "$TAG" -e POSTGRES_USER=furnace \
    -e POSTGRES_PASSWORD=furnace -e POSTGRES_DB=furnace postgres:17-alpine >/dev/null
  docker run --rm --network "$TAG" \
    -v /var/run/docker.sock:/var/run/docker.sock -v "$VMDIR:$VMDIR" -w "$VMDIR/src" \
    -e PG_HOST="$TAG-pg" -e VMDIR="$VMDIR" \
    ghcr.io/astral-sh/uv:python3.12-bookworm bash -euo pipefail -c '
      curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
        | tar -xz -C /usr/local/bin --strip-components=1 docker/docker
      gid=$(stat -c %g /var/run/docker.sock)
      getent group "$gid" >/dev/null || groupadd -g "$gid" dockersock
      useradd -m -u 1001 -G "$(getent group "$gid" | cut -d: -f1)" runner
      for i in $(seq 1 30); do (echo > /dev/tcp/$PG_HOST/5432) 2>/dev/null && break; sleep 1; done
      su runner -s /bin/bash -c "
        set -euo pipefail
        export PATH=/usr/local/bin:\$PATH TMPDIR=$VMDIR/tmp UV_LINK_MODE=copy
        export UV_PROJECT_ENVIRONMENT=/home/runner/venv  # the shared VM path is mounted noexec
        export FURNACE_DATABASE_URL=postgresql+asyncpg://furnace:furnace@$PG_HOST:5432/furnace
        uv sync --frozen
        uv run ruff check .
        uv run ruff format --check .
        uv run lint-imports
        uv run pyright
        uv run alembic -c packages/furnace/src/furnace/db/alembic.ini upgrade head
        uv run pytest -q -m \"not gpu\"
      "'
}

run_web() {
  echo "== web job at $SHA"
  # Its own filesystem, not the shared VM path: node_modules does not fit the VM's small /tmp.
  git archive HEAD apps/web | docker run --rm -i node:24-bookworm bash -euo pipefail -c '
    mkdir -p /src && tar -x -C /src && cd /src/apps/web
    corepack enable >/dev/null
    pnpm install --frozen-lockfile
    pnpm lint
    pnpm exec next typegen && pnpm exec tsc --noEmit
    pnpm build'
}

run_image() {
  echo "== image job at $SHA"
  # the committed tree as the build context (a tar on stdin; -f is a path inside it)
  git archive HEAD | docker build -q -f apps/api/Dockerfile -t "$TAG-api" - >/dev/null
  docker run --rm --entrypoint uv "$TAG-api" run --no-sync python -c "import furnace_api.main"
  docker rmi "$TAG-api" >/dev/null
}

stage_tree
for job in $JOBS; do
  "run_$job"
  echo "== $job: ok"
done
echo "CI (Linux) passed at $SHA: $JOBS"
# the pre-push hook (scripts/hooks/pre-push) allows only commits recorded here, after all jobs
if [ "$JOBS" = "python web image" ]; then git rev-parse HEAD >> "$(git rev-parse --git-dir)/ci-linux-passed"; fi
