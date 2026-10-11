#!/usr/bin/env bash
# Perf gate with intervals (2026-10-11): A/A calibration at two sample sizes, then the R1
# regression and its repair (RQ5) under the interval-based rules. Resumable per step only
# by rerunning it; each step writes its own files. Usage (from the repo root, lab vLLM up):
#   FURNACE_BENCH_DATE=2026-10-11-gate-ci bash bench/run_gate_ci.sh   # log: <dir>/gpu.log
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
DATE="${FURNACE_BENCH_DATE:-$(date -u +%F)-gate-ci}"
export FURNACE_BENCH_DATE="$DATE"
mkdir -p "bench/results/$DATE"
LOG="bench/results/$DATE/gpu.log"
run() {
  echo "=== $* start $(date -u +%T)" >>"$LOG"
  nvidia-smi --query-gpu=pstate,clocks.sm,power.draw,temperature.gpu --format=csv,noheader >>"$LOG" 2>&1
  uv run python "$@" >>"$LOG" 2>&1
  echo "=== $* exit $? $(date -u +%T)" >>"$LOG"
}
run bench/gate_noise.py --trials 12 --out-name gate_noise
run bench/gate_noise.py --trials 6 --request-multiplier 4 --out-name gate_noise_x4
run bench/rq5.py --repeats 3
echo "=== done $(date -u +%T)" >>"$LOG"
