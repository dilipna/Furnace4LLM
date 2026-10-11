# 2026-10-11: perf gate with 95% intervals (bench/run_gate_ci.sh)

Code: commit `6ee6cc1` (interval-based gate from `5e7c066`), working tree clean. Lab vLLM,
Qwen2.5-0.5B-Instruct, RTX 3050 Ti laptop; SM clock 780 MHz in every run (the same clock as
the 2026-10-09 A/A, so the two are comparable). Unrelated containers (`wc26-mlops-*`,
`cal-api`) were running, as in earlier campaigns.

## gate_noise.md: VALID (12 trials, 34 requests per run)

On AC at start (pre-flight 22:58 UTC: "Best performance", not throttled) and at the end
(manifest: on AC, 90%, 80 W GPU limit); every trial took 52-55 s.

- Verdicts: PASS 7/12, INCONCLUSIVE 5/12, false WARN 0/12, false BLOCK 0/12.
- The 95% interval contained the true difference (0) in 12/12; median width 21.4 points.
- Largest A/A change: **+13.4%** (trial 2), and +13.0% (trial 10). The 2026-10-09 A/A
  reported "within 9.7%" from 12 trials; that was one sample, not a bound. Under the point
  rule in use until 2026-10-11 (WARN above 10%), trials 2 and 10 would have been false WARNs
  (2/12). Under the interval rule both are INCONCLUSIVE.

## gate_noise_x4.md: INVALID, kept as recorded (do not use)

Meant to test whether 4x the requests per run (136) narrows the interval. The laptop lost AC
power during this run: the manifest at the end says on battery (78%, GPU limit 30 W), the
battery fell from 90% to 78% between 23:12 and 23:26 UTC, and trials 3-6 took 148-157 s
instead of 131-132 s. When AC was lost cannot be determined, so no trial is usable. The SM
clock read 780 MHz throughout, but the power limit changed (80 W to 30 W). `gate_noise.py`
checked power only at start; since commit `767c2bf` it checks after every trial and stops.

Observation that motivated a re-run (not a result): the spread between runs of the same
side, not the number of requests in a run, dominates the interval, so more runs rather than
more requests per run is the likely fix. To be measured on AC.

## rq5: NOT RUN

`rq5.py` refused to start: "refusing to benchmark on battery". Repair under the interval
acceptance rule is therefore not measured yet; the most recent repair result remains
`2026-10-09-gate-warmup-v2/rq5.md` (point rule: 3/3 verified at -2.0% to +8.5% vs main).
