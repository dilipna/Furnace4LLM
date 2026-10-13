# Optimizer grid and independent confirmation (2026-10-13)

Design and decision rules fixed before any measurement (`docs/optimizer.md`; confirmation
rules added before the grid). Run by `bench/run_remaining_gpu.sh` after RQ5, 18:37-19:21 UTC.
Pre-run conditions `conditions/2026-10-13T183741Z.json`: on AC, vLLM image
`sha256:8a69ffad...`, measurement code clean at **6efebfd**, 780 MHz under the probe load.
(The 03:15 UTC attempt refused to start on battery, `conditions/2026-10-13T031547Z.json`; no
grid result exists from it.)

## Result: no change is recommended

- **Grid** (`optimizer/optimizer.md`): 5 of 8 configs feasible. Highest median SLO goodput:
  0.5B, prefix caching on, max-num-seqs 8, 8.34 req/s (range 7.37-8.34), against the
  baseline (0.5B, caching on, seqs 32) at 8.30 (7.36-8.37). The ranges overlap, so by the
  pre-declared rule the recommendation is **keep the baseline**. Infeasible: both 1.5B-AWQ
  configs with caching off (p95 TTFT about 1.1 s > 500 ms SLO) and 0.5B caching off seqs 8
  (facts quality not shown within the 5-point tolerance: -1.6, interval -7.8 to +4.7).
- **Independent confirmation** (`optimizer/confirm.md`; 8 fresh launches A B B A A B B A, new
  seeds): **inconclusive**. Goodput B vs A +3.8% (90% interval -8.8 to +18.2); p95 TTFT +1.0%
  (-6.7 to +9.5); quality facts +0.0 pts (-4.0 to +4.0), citations +0.0. No improvement is
  claimed.
- What the grid does show, as measured on this laptop: turning prefix caching off roughly
  halves goodput for the 0.5B model (4.4-4.7 vs 8.3 req/s) and pushes the 1.5B-AWQ model past
  the 500 ms p95 SLO; 1.5B-AWQ scores higher on both deterministic quality checks (facts
  85.7% vs 74.6%, citations 12.7% vs 0.0%) at about 77% of the 0.5B goodput with caching on.

## Clocks (not set; chosen by the driver)

| config | SM MHz, 3 runs |
|---|---|
| 0.5B caching on, seqs 8 / 32 (pick, baseline) | 780 / 780 |
| 1.5B-AWQ caching on, seqs 8 / 32 | 781-782 |
| 0.5B caching off, seqs 8 / 32 | 796-847 / 791-810 |
| 1.5B-AWQ caching off, seqs 8 / 32 | 1,421-1,644 / 1,349-1,621 |

All eight confirmation launches ran at 780 MHz. The driver raised the clock only for the
heaviest (caching-off) configs, which makes them look faster than they would at 780 MHz; they
were slower or infeasible anyway, so no conclusion depends on it. The pick and the baseline
were compared at the same clock, in the grid and in the confirmation.

## Limits

One GPU, one workload (W1), concurrency 8; quality is two deterministic checks, not judged
answer quality; the grid's three runs per config are consecutive on one container. Cost is
N/A (no $/GPU-hour on a self-hosted laptop).

## Operator activity during the run

File reads, greps, `git status`/`git log`, a directory comparison and one `python -c` that
printed a stored JSON field (about 0.1 s), between 18:40 and 19:10 UTC. No test, lint, build
or analysis script ran.
