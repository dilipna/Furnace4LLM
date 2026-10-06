#!/usr/bin/env bash
# Run the GPU part of FurnaceBench in order (RQ4 -> RQ3 -> RQ5 -> report), resumably.
# Each driver skips work already stored in the results directory, so rerunning continues
# where a previous run stopped. Usage (from the repo root):
#   FURNACE_BENCH_DATE=2026-10-06 bash bench/run_gpu.sh            # log: bench/results/<date>/gpu.log
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
export HF_HOME_HOST="${HF_HOME_HOST:-$HOME/.cache/huggingface}"
DATE="${FURNACE_BENCH_DATE:-$(date -u +%F)}"
export FURNACE_BENCH_DATE="$DATE"
mkdir -p "bench/results/$DATE"
LOG="bench/results/$DATE/gpu.log"

wait_lab() {
  docker compose --profile gpu up -d vllm >>"$LOG" 2>&1
  for _ in $(seq 1 120); do
    curl -sf localhost:8100/v1/models >/dev/null && { echo "lab ready $(date -u +%T)" >>"$LOG"; return 0; }
    sleep 5
  done
  echo "lab NOT ready" >>"$LOG"
  return 1
}

for step in rq4 rq3 rq5; do
  [ "$step" != rq4 ] && { wait_lab || exit 1; }
  echo "=== $step start $(date -u +%T)" >>"$LOG"
  uv run python "bench/$step.py" >>"$LOG" 2>&1
  echo "=== $step exit $? $(date -u +%T)" >>"$LOG"
done
uv run python bench/report.py >>"$LOG" 2>&1
echo "=== done $(date -u +%T)" >>"$LOG"
