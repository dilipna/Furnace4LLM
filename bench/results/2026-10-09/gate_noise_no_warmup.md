# Perf-gate noise calibration (A/A), gate WITHOUT warmup (before the fix)

F1 main vs an identical copy of F1 main, 12 gate runs, each 3 interleaved repeats per side at concurrency 8 (the real gate path). Any change below is noise.

| trial | p95 TTFT a (ms) | p95 TTFT b (ms) | change | runs separated | verdict (policy) | SM MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 89.0 | 87.3 | -1.8% | no | pass | 726-780 |
| 2 | 175.7 | 112.7 | -35.9% | no | pass | 739-780 |
| 3 | 201.9 | 97.4 | -51.7% | no | pass | 726-782 |
| 4 | 194.9 | 88.0 | -54.8% | no | pass | 730-781 |
| 5 | 205.1 | 100.7 | -50.9% | no | pass | 722-780 |
| 6 | 202.2 | 80.6 | -60.2% | no | pass | 726-780 |
| 7 | 204.5 | 212.6 | +4.0% | no | pass | 723-780 |
| 8 | 207.2 | 201.0 | -3.0% | no | pass | 742-780 |
| 9 | 214.6 | 189.0 | -11.9% | no | pass | 726-780 |
| 10 | 230.8 | 163.0 | -29.4% | no | pass | 726-780 |
| 11 | 213.1 | 89.1 | -58.2% | no | pass | 726-780 |
| 12 | 202.6 | 90.2 | -55.5% | no | pass | 726-780 |

Change: median -43.4%, min -60.2%, max +4.0%; |change| median 43.4%, max 60.2%.
Policy at the time: warn > 10.0%, block > 25.0% and runs separated.
False WARN: 0/12; false BLOCK: 0/12; separated by chance: 0/12.
