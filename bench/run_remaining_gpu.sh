#!/usr/bin/env bash
# Everything the Oct 12 follow-up still owes the GPU, resumable: the gate validation sets
# (kept trials are not rerun), the report, RQ5 under the frozen gate, then the optimizer grid
# (configs already measured are skipped). Laptop on AC; start it through the keep-awake
# launcher so Windows does not idle-sleep mid-run. From PowerShell (single quotes keep $PATH
# for bash; keep the window open until it prints "job exited"):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\furnace\scripts\run_awake.ps1 -Bash 'export PATH=/c/Users/Dilip/.local/bin:$PATH; cd /c/dev/furnace && bash bench/run_remaining_gpu.sh'
# About 2 hours. Logs: bench/results/2026-10-12-gate-validation/gpu.log and optimizer.log
set -u
cd "$(dirname "$0")/.."
# Docker Desktop, Postgres and the lab vLLM do not survive a sleep: bring them up, or stop.
if ! docker info >/dev/null 2>&1; then
  "/c/Users/Dilip/AppData/Local/Programs/DockerDesktop/Docker Desktop.exe" >/dev/null 2>&1 &
  for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
docker info >/dev/null 2>&1 || { echo "Docker is not running; stopping" >&2; exit 1; }
docker compose up -d postgres >/dev/null
HF_HOME_HOST="C:/Users/Dilip/.cache/huggingface" docker compose --profile gpu up -d vllm >/dev/null
for _ in $(seq 1 90); do curl -sf http://localhost:8100/v1/models >/dev/null && break; sleep 5; done
curl -sf http://localhost:8100/v1/models >/dev/null || { echo "lab vLLM did not come up; stopping" >&2; exit 1; }
export RESUME_NOTE="${RESUME_NOTE:-the machine went to sleep (Kernel-Power 42 at 19:54 UTC on 2026-10-12) after trial 14; resumed later on AC}"
FURNACE_BENCH_DATE=2026-10-12-gate-validation bash bench/run_gate_validation.sh
FURNACE_BENCH_DATE=2026-10-12-optimizer PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 \
  uv run python bench/optimize.py >>bench/results/2026-10-12-gate-validation/optimizer.log 2>&1
