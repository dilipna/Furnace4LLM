# Perf-gate validation (fresh runs, protocol in docs/gate-revision.md)

| set | counted trials/planned | PASS | INCONCLUSIVE | WARN | BLOCK | error | WARN+BLOCK (exact 95% CI of the rate) | median change | range of change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1_aa | 11/24 | 7 | 4 | 0 | 0 | 0 | 0/11 (0%-28%) | -0.3% | -15.0% to +5.4% |
| v1_aa incl. affected | 14 (all kept) | 10 | 4 | 0 | 0 | 0 | 0/14 (0%-23%) | -0.0% | -15.0% to +5.4% |

## Affected trials, interruptions, discards, errors

- v1_aa trial 6 affected by competing work, left out of the first row and replaced (result kept): ruff check over packages, ruff format and the bench/correlation.py analysis ran 19:45:43-19:46:10 inside the trial (19:45:39-19:46:29)
- v1_aa trial 9 affected by competing work, left out of the first row and replaced (result kept): pytest test_repair+test_gate_stats with the Docker sandbox ran 19:48:22-19:49:13 (26 passed in 35.69 s): ~44 s of trial 9 (19:48:14-19:49:06), ~5 s of trial 10 (19:49:08-19:49:58)
- v1_aa trial 10 affected by competing work, left out of the first row and replaced (result kept): pytest test_repair+test_gate_stats with the Docker sandbox ran 19:48:22-19:49:13 (26 passed in 35.69 s): ~44 s of trial 9 (19:48:14-19:49:06), ~5 s of trial 10 (19:49:08-19:49:58)
- v1_aa: run interrupted after trial 2, resumed at 2026-10-12T19:42:59Z (the machine slept or Docker Desktop stopped after trial 2 (about 05:22 UTC); every Furnace process was gone at 19:18 UTC; resumed on AC at 780 MHz); earlier trials kept
