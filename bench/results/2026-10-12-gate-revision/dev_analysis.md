# Perf-gate revision: development analysis (unchanged-code data only)

20 A/A trials, 152 runs, [34] measured requests per run, c=8, lab vLLM, 780 MHz. Raw data: `2026-10-11-gate-ci/gate_noise.json` (3 runs per side), `2026-10-12-gate-ci/gate_noise_r5.json` (5 runs per side). Excluded: `gate_noise_x4` (AC lost mid-run), 2026-10-09 studies (no per-request samples).

## Dependence

- Within a run, 62% of consecutive requests have TTFT within 3% of the previous one (closed-loop waves share a scheduler step); lag-1 autocorrelation of log TTFT 0.33. Requests in a run are not independent; a 34-request run holds roughly 4-5 waves.
- Run-level geometric mean (log scale): SD across runs 0.054 within a trial, SD of trial means 0.027 (ICC 0.20); correlation of consecutive runs -0.19. Run-level SD of log p95 is 0.112 vs 0.056 for the geometric mean.
- Pairing runs by repeat does not help: SD of paired differences 0.076 vs 0.065 if unpaired.

## Statistic and aggregation (SD of the A/A log ratio, lower is better)

| statistic | aggregate over runs | SD of log ratio | largest |change| (%) |
| --- | --- | ---: | ---: |
| p95 | median of runs | 0.053 | 13.4 |
| p95 | pooled requests | 0.167 | 102.3 |
| p90 | median of runs | 0.058 | 19.7 |
| p90 | pooled requests | 0.118 | 57.8 |
| p75 | median of runs | 0.044 | 10.2 |
| p75 | pooled requests | 0.087 | 38.9 |
| p50 | median of runs | 0.055 | 11.9 |
| p50 | pooled requests | 0.054 | 12.6 |
| mean | median of runs | 0.036 | 9.6 |
| mean | pooled requests | 0.055 | 21.6 |
| gmean | median of runs | 0.035 | 9.5 |
| gmean | pooled requests | 0.044 | 14.9 |
| trim | median of runs | 0.035 | 9.4 |
| trim | pooled requests | 0.044 | 13.5 |

Pooling requests across runs is the worst for tail percentiles (a single slow run sets the pooled p95); it only helps location statistics slightly.

## Interval for the current statistic (p95), 95% intervals

Stored hierarchical-bootstrap interval, median width 22.8 points; run-level Welch t interval on the same runs, median width 26.8 points. The bootstrap over 3 or 5 runs is about 15% narrower than the run-level t interval: a modest difference, but in the optimistic direction, because few runs give few distinct resamples.

## Frozen rule on the development data (descriptive: selected on these data)

Tolerance 10%, two-sided 90% t interval on run-level values (5% per tail). Every k-run subset of each trial's runs; subsets from one trial are correlated.

| statistic | runs/side | subsets | PASS | INCONCLUSIVE | FAIL (false) | median interval width (pts) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gmean | 3 | 92 | 87% | 13% | 0% | 10.7 |
| gmean | 4 | 40 | 90% | 10% | 0% | 8.2 |
| gmean | 5 | 8 | 88% | 12% | 0% | 7.0 |
| p95 | 3 | 92 | 18% | 82% | 0% | 28.3 |
| p95 | 4 | 40 | 28% | 72% | 0% | 21.1 |
| p95 | 5 | 8 | 38% | 62% | 0% | 18.1 |
