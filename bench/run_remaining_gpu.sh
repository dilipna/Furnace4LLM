#!/usr/bin/env bash
# Everything the Oct 12 follow-up still owes the GPU, resumable: the gate validation sets
# (kept trials are not rerun; affected trials are replaced), the report, RQ5 under the frozen
# gate, the optimizer grid (configs already measured are skipped), then the optimizer's
# independent confirmation run (launches already done are skipped).
# Laptop on AC, nothing else running on it. Start it through the keep-awake launcher, from
# PowerShell, and keep that window open until it prints "job exited":
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\furnace\scripts\run_awake.ps1 -Script bench/run_remaining_gpu.sh
# Do not choose Sleep while it runs (the launcher cannot block Windows' own Sleep command).
# About 2.5 hours. Logs: bench/results/2026-10-12-gate-validation/gpu.log and optimizer.log
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
LOG=bench/results/2026-10-12-gate-validation/gpu.log
note() { echo "=== $* $(date -u +%FT%TZ)" >>"$LOG"; }
# Docker Desktop, Postgres and the lab vLLM do not survive a sleep: bring them up, or stop.
if ! docker info >/dev/null 2>&1; then
  "/c/Users/user/AppData/Local/Programs/DockerDesktop/Docker Desktop.exe" >/dev/null 2>&1 &
  for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
docker info >/dev/null 2>&1 || { echo "Docker is not running; stopping" >&2; exit 1; }
docker compose up -d postgres >/dev/null
HF_HOME_HOST="C:/Users/user/.cache/huggingface" docker compose --profile gpu up -d vllm >/dev/null
for _ in $(seq 1 90); do curl -sf -m 5 http://localhost:8100/v1/models >/dev/null && break; sleep 5; done
curl -sf -m 5 http://localhost:8100/v1/models >/dev/null || { echo "lab vLLM did not come up; stopping" >&2; exit 1; }

# Frozen conditions (AC, pinned image, clean measurement code, 780 MHz under load): stop if not met.
note "conditions check"
if ! FURNACE_BENCH_DATE=2026-10-12-gate-validation uv run python bench/conditions.py \
  --label "before the remaining validation trials" >>"$LOG" 2>&1; then
  note "conditions NOT met; stopping (see the lines above)"
  echo "conditions not met; see $LOG" >&2
  exit 1
fi

# Only describes why V1 was interrupted; sets that have no trials yet ignore it.
export RESUME_NOTE="${RESUME_NOTE:-Windows Sleep was chosen at 19:54 UTC on 2026-10-12 (Kernel-Power 42 and 187, winlogon) after trial 14; trial 15 left no record; resumed on AC after the conditions check, with replacements for affected trials 6, 9, 10}"
FURNACE_BENCH_DATE=2026-10-12-gate-validation bash bench/run_gate_validation.sh
note "power after validation and RQ5: $(uv run python -c 'import sys; sys.path.insert(0, "bench"); from common import power_state; print(power_state())')"
FURNACE_BENCH_DATE=2026-10-12-optimizer uv run python bench/conditions.py \
  --label "before the optimizer grid" >>"$LOG" 2>&1 \
  || note "conditions check before the optimizer FAILED (recorded above); the optimizer checks AC itself"
# The confirmation needs a finished grid and selection; it does not start after a stopped grid.
FURNACE_BENCH_DATE=2026-10-12-optimizer uv run python bench/optimize.py \
  >>bench/results/2026-10-12-gate-validation/optimizer.log 2>&1 \
  && FURNACE_BENCH_DATE=2026-10-12-optimizer uv run python bench/optimize.py --confirm \
    >>bench/results/2026-10-12-gate-validation/optimizer.log 2>&1
note "all done (exit $?)"
