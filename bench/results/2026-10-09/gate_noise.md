# Perf-gate noise calibration (A/A)

F1 main vs an identical copy of F1 main, 12 gate runs, each 3 interleaved repeats per side at concurrency 8 (the real gate path). Any change below is noise.

| trial | p95 TTFT a (ms) | p95 TTFT b (ms) | change | runs separated | verdict (policy) | SM MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 88.4 | 84.6 | -4.3% | no | pass | 780-780 |
| 2 | 90.5 | 88.7 | -2.1% | no | pass | 780-780 |
| 3 | 86.2 | 94.5 | +9.7% | no | pass | 780-780 |
| 4 | 84.3 | 90.5 | +7.3% | yes | pass | 780-780 |
| 5 | 85.0 | 85.0 | -0.1% | no | pass | 780-780 |
| 6 | 85.0 | 88.6 | +4.1% | no | pass | 780-780 |
| 7 | 85.2 | 89.2 | +4.7% | no | pass | 780-780 |
| 8 | 88.7 | 84.7 | -4.6% | no | pass | 780-780 |
| 9 | 84.1 | 86.5 | +2.8% | no | pass | 780-780 |
| 10 | 88.3 | 84.5 | -4.3% | no | pass | 780-780 |
| 11 | 87.8 | 88.0 | +0.3% | no | pass | 780-780 |
| 12 | 84.8 | 86.5 | +2.0% | no | pass | 780-780 |

Change: median +1.1%, min -4.6%, max +9.7%; |change| median 4.2%, max 9.7%.
Policy at the time: warn > 10.0%, block > 25.0% and runs separated.
False WARN: 0/12; false BLOCK: 0/12; separated by chance: 1/12.
