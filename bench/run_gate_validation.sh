#!/usr/bin/env bash
# Fresh validation of the revised perf gate (protocol: docs/gate-revision.md, sections 5 and 7).
# Run from the repo root with the lab vLLM up and the laptop on AC power:
#   FURNACE_BENCH_DATE=2026-10-12-gate-validation bash bench/run_gate_validation.sh
# Log: bench/results/<date>/gpu.log. Each set writes its own files and the chain continues if
# one stops (a stop is reported by `gate_validate.py summarize`, never hidden).
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
DATE="${FURNACE_BENCH_DATE:-$(date -u +%F)-gate-validation}"
export FURNACE_BENCH_DATE="$DATE"
mkdir -p "bench/results/$DATE"
LOG="bench/results/$DATE/gpu.log"
# RESUME_NOTE: set it to continue sets whose trials were interrupted (recorded in each set).
RESUME=()
if [ -n "${RESUME_NOTE:-}" ]; then RESUME=(--resume-note "$RESUME_NOTE"); fi
run() {
  echo "=== $* start $(date -u +%T)" >>"$LOG"
  nvidia-smi --query-gpu=pstate,clocks.sm,power.draw,temperature.gpu --format=csv,noheader >>"$LOG" 2>&1
  uv run python "$@" >>"$LOG" 2>&1
  echo "=== $* exit $? $(date -u +%T)" >>"$LOG"
}
run bench/gate_validate.py run --set v1_aa "${RESUME[@]}"
run bench/gate_validate.py run --set v2_restored "${RESUME[@]}"
run bench/gate_validate.py run --set v3a_r1 "${RESUME[@]}"
run bench/gate_validate.py run --set v3b_r2 "${RESUME[@]}"
run bench/gate_validate.py run --set v3c_topk4 "${RESUME[@]}"
run bench/gate_validate.py run --set v3c_topk8 "${RESUME[@]}"
run bench/gate_validate.py summarize
# V4: the repair loop under the frozen gate. Reported as measured; not a criterion for the gate.
run bench/rq5.py --repeats 3
echo "=== done $(date -u +%T)" >>"$LOG"
