# Perf-gate validation (fresh runs, protocol in docs/gate-revision.md)

| set | counted trials/planned | PASS | INCONCLUSIVE | WARN | BLOCK | error | WARN+BLOCK (exact 95% CI of the rate) | median change | range of change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1_aa | 24/24 | 18 | 6 | 0 | 0 | 0 | 0/24 (0%-14%) | -0.0% | -15.0% to +5.4% |
| v1_aa incl. affected | 27 (all kept) | 21 | 6 | 0 | 0 | 0 | 0/27 (0%-13%) | +0.2% | -15.0% to +5.4% |
| v2_restored | 12/12 | 11 | 1 | 0 | 0 | 0 | 0/12 (0%-26%) | -1.1% | -2.7% to +4.4% |
| v3a_r1 | 6/6 | 0 | 0 | 0 | 6 | 0 | 6/6 (54%-100%) | +612.7% | +608.9% to +620.6% |
| v3b_r2 | 6/6 | 1 | 5 | 0 | 0 | 0 | 0/6 (0%-46%) | +7.2% | +1.1% to +54.5% |
| v3c_topk4 | 6/6 | 1 | 5 | 0 | 0 | 0 | 0/6 (0%-46%) | +4.3% | +2.2% to +6.5% |
| v3c_topk8 | 6/6 | 1 | 5 | 0 | 0 | 0 | 0/6 (0%-46%) | +6.5% | +4.4% to +33.0% |

## Affected trials, interruptions, discards, errors

- v1_aa trial 6 affected by competing work, left out of the first row and replaced (result kept): ruff check over packages, ruff format and the bench/correlation.py analysis ran 19:45:43-19:46:10 inside the trial (19:45:39-19:46:29)
- v1_aa trial 9 affected by competing work, left out of the first row and replaced (result kept): pytest test_repair+test_gate_stats with the Docker sandbox ran 19:48:22-19:49:13 (26 passed in 35.69 s): ~44 s of trial 9 (19:48:14-19:49:06), ~5 s of trial 10 (19:49:08-19:49:58)
- v1_aa trial 10 affected by competing work, left out of the first row and replaced (result kept): pytest test_repair+test_gate_stats with the Docker sandbox ran 19:48:22-19:49:13 (26 passed in 35.69 s): ~44 s of trial 9 (19:48:14-19:49:06), ~5 s of trial 10 (19:49:08-19:49:58)
- v1_aa: run interrupted after trial 2, resumed at 2026-10-12T19:42:59Z (the machine slept or Docker Desktop stopped after trial 2 (about 05:22 UTC); every Furnace process was gone at 19:18 UTC; resumed on AC at 780 MHz); earlier trials kept
- v1_aa: run interrupted after trial 14, resumed at 2026-10-13T02:24:56Z (Windows Sleep was chosen at 19:54 UTC on 2026-10-12 (Kernel-Power 42 and 187, winlogon) after trial 14; trial 15 left no record; resumed on AC after the conditions check, with replacements for affected trials 6, 9, 10); earlier trials kept
