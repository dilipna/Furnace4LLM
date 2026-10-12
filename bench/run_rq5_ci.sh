#!/usr/bin/env bash
# RQ5 (failing-test-first repair) under the interval-based acceptance rule, then an A/A
# calibration with 5 interleaved runs per side (does more runs narrow the interval?).
# Both drivers check AC power after every attempt/trial and stop if it was lost.
# Usage (repo root, lab vLLM up, on AC):
#   FURNACE_BENCH_DATE=2026-10-12-gate-ci bash bench/run_rq5_ci.sh   # log: <dir>/gpu.log
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
run bench/rq5.py --repeats 3
run bench/gate_noise.py --trials 8 --repeats 5 --out-name gate_noise_r5
echo "=== done $(date -u +%T)" >>"$LOG"
