# Perf-gate noise calibration (A/A)

F1 main vs an identical copy of F1 main, 6 gate runs, each 3 interleaved repeats per side at concurrency 8 (the real gate path), 136 measured requests per run. Any change below is noise.

| trial | p95 TTFT a (ms) | p95 TTFT b (ms) | change | 95% CI | runs separated | verdict (policy) | SM MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 85.7 | 84.7 | -1.2% | -28.4% to +27.4% | no | inconclusive | 780-780 |
| 2 | 84.3 | 84.7 | +0.4% | -25.6% to +22.8% | no | inconclusive | 780-780 |
| 3 | 109.1 | 114.5 | +5.0% | -22.4% to +40.1% | no | inconclusive | 780-780 |
| 4 | 107.0 | 106.6 | -0.3% | -25.7% to +18.0% | no | inconclusive | 780-780 |
| 5 | 101.8 | 99.1 | -2.6% | -13.5% to +9.7% | no | pass | 780-780 |
| 6 | 103.5 | 111.2 | +7.4% | -3.8% to +28.2% | yes | inconclusive | 780-780 |

Change: median +0.1%, min -2.6%, max +7.4%; |change| median 1.9%, max 7.4%.
Policy at the time: tolerance 10.0%, block > 25.0% and runs separated. Decision method: hierarchical bootstrap (runs, then requests within runs), 95% interval.
Verdicts: pass 1/6, inconclusive 5/6 (noise too large to decide), false WARN 0/6, false BLOCK 0/6; separated by chance: 1/6.
Interval check: the 95% interval contains 0 (the true A/A difference) in 6/6 trials; width median 46.1 percentage points, max 62.5.
