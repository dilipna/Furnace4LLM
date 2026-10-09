# RQ5 rerun with the warmed-up perf gate (2026-10-09), suffix strategy only

Same RQ5 procedure as 2026-10-06, with one change to the perf gate: each measured run is now
preceded by an unmeasured warmup wave (see `../2026-10-09/gate_noise*.md`: without it the first
wave after idle set the p95, and the base revision, always measured first, read ~2.4x slower).

Result: the only repair strategy then (`move_dynamic_to_suffix`) removes ~95% of R1's cost
(p95 TTFT ~910 -> ~125 ms) but stays +40-47% above base (~87 ms): the gate blocks it, 0/3
verified. The 2026-10-06 "3/3 verified" was measured with the cold-start-biased gate.
Kept unchanged as evidence; the follow-up with a second strategy is `../2026-10-09-gate-warmup-v2/`.
