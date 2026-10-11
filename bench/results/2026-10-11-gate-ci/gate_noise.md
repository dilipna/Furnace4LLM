# Perf-gate noise calibration (A/A)

F1 main vs an identical copy of F1 main, 12 gate runs, each 3 interleaved repeats per side at concurrency 8 (the real gate path), 34 measured requests per run. Any change below is noise.

| trial | p95 TTFT a (ms) | p95 TTFT b (ms) | change | 95% CI | runs separated | verdict (policy) | SM MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 89.3 | 86.9 | -2.7% | -52.5% to +4.6% | no | pass | 780-780 |
| 2 | 79.6 | 90.2 | +13.4% | -7.1% to +26.7% | no | inconclusive | 780-780 |
| 3 | 87.6 | 88.2 | +0.8% | -3.2% to +4.8% | no | pass | 780-780 |
| 4 | 88.4 | 92.2 | +4.2% | -10.9% to +11.1% | no | inconclusive | 780-780 |
| 5 | 86.3 | 84.5 | -2.0% | -10.7% to +8.1% | no | pass | 780-780 |
| 6 | 83.5 | 88.4 | +5.8% | -6.9% to +8.0% | no | pass | 780-780 |
| 7 | 95.2 | 93.0 | -2.3% | -23.8% to +17.0% | no | inconclusive | 780-780 |
| 8 | 97.4 | 107.1 | +10.0% | -8.7% to +21.5% | no | inconclusive | 780-780 |
| 9 | 107.3 | 104.2 | -2.9% | -14.0% to +2.4% | no | pass | 780-780 |
| 10 | 102.3 | 115.6 | +13.0% | -1.3% to +19.9% | no | inconclusive | 780-780 |
| 11 | 98.3 | 97.1 | -1.2% | -13.1% to +8.6% | no | pass | 780-780 |
| 12 | 99.2 | 96.7 | -2.5% | -5.9% to +5.0% | no | pass | 780-780 |

Change: median -0.2%, min -2.9%, max +13.4%; |change| median 2.8%, max 13.4%.
Policy at the time: tolerance 10.0%, block > 25.0% and runs separated. Decision method: hierarchical bootstrap (runs, then requests within runs), 95% interval.
Verdicts: pass 7/12, inconclusive 5/12 (noise too large to decide), false WARN 0/12, false BLOCK 0/12; separated by chance: 0/12.
Interval check: the 95% interval contains 0 (the true A/A difference) in 12/12 trials; width median 21.4 percentage points, max 57.1.
