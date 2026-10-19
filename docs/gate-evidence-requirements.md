# Gate evidence requirements

Implementation correction, 2026-10-18. This supplements the frozen
[gate method](gate-revision.md); it does not change the statistic, confidence level,
latency thresholds, or historical experiment results.

## Problem and corrected behavior

The statistical gate already required three runs per side, but missing or undersized
per-request samples selected a legacy p95 point rule instead. A single run with 19
successful requests could therefore receive PASS. Repair acceptance had a similar
fallback: a candidate within the baseline's point budget could be accepted without
evidence that it improved on the PR head. For example, baseline/head/candidate p95 values
of 100/110/120 ms accepted the slower candidate.

The corrected rules are:

| Evidence | Gate behavior |
|---|---|
| Every run has at least 20 finite, positive timing samples; at least three runs per side under the default policy | Existing run-level Welch interval and thresholds |
| Valid samples, but fewer than the policy's minimum number of runs | INCONCLUSIVE; no interval |
| Missing, undersized, or invalid samples; finite positive p95 summaries available for every run | INCONCLUSIVE; p95 summaries displayed for diagnosis only |
| No usable timing summaries | ERROR, never PASS |
| Failed-request rate increases by more than one percentage point | BLOCK regardless of whether timing evidence is usable |

An incomplete run invalidates the interval comparison; it is not silently dropped.
INCONCLUSIVE maps to a neutral GitHub check. Summary diagnostics are labeled p95,
not geometric-mean TTFT. Base and head run counts are reported separately.

## Repair acceptance

A candidate needs valid, finite, ordered intervals against **both** the PR head and
baseline. Its interval upper bound must be below zero against the head and below the
blocking threshold against the baseline. A comparison error or a candidate blocking
verdict rejects the repair. Missing intervals cannot be replaced by a point estimate.

An INCONCLUSIVE baseline comparison can still be acceptable when its valid interval
straddles the 10% tolerance but remains below the 25% blocking threshold, provided the
candidate is demonstrably faster than the head. This preserves the original repair
contract; it does not turn every INCONCLUSIVE into a rejection.

## Reproduce the checks

From the repository root, with Python 3.12 and the locked dependencies:

```sh
uv sync --frozen
uv run pytest -q packages/furnace/tests/test_gate_stats.py packages/furnace/tests/test_guard_execute.py packages/furnace/tests/test_tdist.py bench/tests/test_gate_validate.py
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pyright
```

The tests exercise sample sufficiency, NaN/infinity and nonpositive samples, mixed
complete/incomplete runs, absent and malformed repair intervals, error propagation,
failure-rate precedence, the complete repair decision function, and conversion to a
neutral GitHub check. Synthetic timings establish decision logic, not GPU performance.
Docker-backed repair execution and fresh inference measurements remain separate checks.

## What this does and does not prove

This correction makes the implementation enforce its stated evidence requirements.
It does not expand the external validity of the stored RTX 3050 Ti / Qwen2.5-0.5B
experiments. The gate measures geometric-mean TTFT; p95 remains advisory. The existing
6/6 severe-regression detections and 0 false failures across 36 unchanged/restored trials
(including seven inconclusive results) remain bounded historical observations, not a
guarantee across applications or hardware.

Before making a broader portfolio claim, freeze a second supported workload and evaluation
protocol, record its baseline/model/hardware and independent run counts, then report all
outcomes, including failures and inconclusive comparisons. Keep that experiment separate
from this logic fix so changing the gate cannot be mistaken for new benchmark evidence.
