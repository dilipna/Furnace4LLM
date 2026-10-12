# Perf-gate noise calibration (A/A)

F1 main vs an identical copy of F1 main, 8 gate runs, each 5 interleaved repeats per side at concurrency 8 (the real gate path), 34 measured requests per run. Any change below is noise.

| trial | p95 TTFT a (ms) | p95 TTFT b (ms) | change | 95% CI | runs separated | verdict (policy) | SM MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 96.7 | 100.9 | +4.3% | -12.9% to +30.5% | no | inconclusive | 780-780 |
| 2 | 99.2 | 105.0 | +5.8% | -10.2% to +12.5% | no | inconclusive | 780-780 |
| 3 | 98.1 | 98.2 | +0.2% | -10.0% to +16.3% | no | inconclusive | 780-780 |
| 4 | 97.2 | 100.9 | +3.8% | -5.2% to +13.1% | no | inconclusive | 780-780 |
| 5 | 104.6 | 97.2 | -7.1% | -15.7% to +7.1% | no | pass | 780-780 |
| 6 | 101.8 | 103.3 | +1.5% | -16.0% to +18.8% | no | inconclusive | 780-780 |
| 7 | 100.6 | 102.3 | +1.6% | -15.4% to +13.7% | no | inconclusive | 780-780 |
| 8 | 100.8 | 100.3 | -0.6% | -10.3% to +19.9% | no | inconclusive | 780-780 |

Change: median +1.6%, min -7.1%, max +5.8%; |change| median 2.7%, max 7.1%.
Policy at the time: tolerance 10.0%, block > 25.0% and runs separated. Decision method: hierarchical bootstrap (runs, then requests within runs), 95% interval.
Verdicts: pass 1/8, inconclusive 7/8 (noise too large to decide), false WARN 0/8, false BLOCK 0/8; separated by chance: 0/8.
Interval check: the 95% interval contains 0 (the true A/A difference) in 8/8 trials; width median 27.7 percentage points, max 43.4.
