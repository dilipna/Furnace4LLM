# Perf-gate validation: fresh trials under the frozen rule

Every trial is the real gate path (prompts rendered from each revision in the sandbox, 3 interleaved runs per side, c=8, 34 requests per run). Rule frozen in `docs/gate-revision.md` (6e90c99; implemented 26fa8eb; sizes for the graded sets fixed in 9d80db8 before any trial). The last column applies the rule that was replaced to the same raw samples. Trials affected by competing work on the machine are left out of the primary row, replaced, and shown again in an 'incl. affected' row (rule: `../NOTES.md`). SM clock across all trials: 780-828 MHz.

| set | true change | trials | PASS | INCONCL. | WARN | BLOCK | FAIL = WARN+BLOCK (exact 95% CI) | measured change, median (range) | interval width, median (pts) | interval contains 0 | old rule on same data: P/I/W/B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1_aa | none (unchanged) | 24/24 | 18 | 6 | 0 | 0 | 0/24 (0%-14%) | -0.0% (-15.0 to +5.4) | 11.9 | 23/24 | 8/16/0/0 |
| v1_aa, incl. affected trials [6, 9, 10] | none (unchanged) | 27/24 | 21 | 6 | 0 | 0 | 0/27 (0%-13%) | +0.2% (-15.0 to +5.4) | 11.8 | 26/27 | 11/16/0/0 |
| v2_restored | none (unchanged) | 12/12 | 11 | 1 | 0 | 0 | 0/12 (0%-26%) | -1.1% (-2.7 to +4.4) | 14.6 | 11/12 | 5/7/0/0 |
| v3c_topk4 | +12.9% | 6/6 | 1 | 5 | 0 | 0 | 0/6 (0%-46%) | +4.3% (+2.2 to +6.5) | 11.6 | – | 4/2/0/0 |
| v3c_topk8 | +18.2% | 6/6 | 1 | 5 | 0 | 0 | 0/6 (0%-46%) | +6.5% (+4.4 to +33.0) | 15.1 | – | 1/5/0/0 |
| v3b_r2 | about +30% (depth 12) | 6/6 | 1 | 5 | 0 | 0 | 0/6 (0%-46%) | +7.2% (+1.1 to +54.5) | 11.3 | – | 0/6/0/0 |
| v3a_r1 | about +800% (earlier studies) | 6/6 | 0 | 0 | 0 | 6 | 6/6 (54%-100%) | +612.7% (+608.9 to +620.6) | 42.7 | – | 0/0/0/6 |

Unchanged code (V1 + V2 together): false FAIL 0/36 (exact 95% CI 0.0% to 9.7%), PASS 29/36.
The same, including affected trials: false FAIL 0/39 (exact 95% CI 0.0% to 9.0%), PASS 32/39.

Pre-declared targets (primary rows):
- v1_aa: false FAIL 0% (target <= 10%: met), PASS 75% (target >= 70%: met)
- v2_restored: false FAIL 0% (target <= 10%: met), PASS 92% (target >= 70%: met)
- v3a_r1: BLOCK in 6/6 (target: all: met)

## Tail latency (p95), reported separately; advisory, never decides a verdict

Same trials and runs: each run's p95 TTFT, compared with the same run-level 90% Welch interval. 'Ruled out' = interval upper bound <= 10%; 'established' = lower bound > 10%.

| set | trials | p95 change, median (range) | interval width, median (pts) | tail regression > 10% ruled out | established | unresolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v1_aa | 24 | +0.2% (-20.1 to +7.1) | 21.6 | 11 | 0 | 13 |
| v2_restored | 12 | -0.5% (-8.3 to +5.9) | 26.5 | 2 | 0 | 10 |
| v3c_topk4 | 6 | +2.9% (+0.0 to +8.2) | 13.1 | 3 | 0 | 3 |
| v3c_topk8 | 6 | +5.6% (+2.3 to +37.1) | 18.3 | 1 | 0 | 5 |
| v3b_r2 | 6 | +6.5% (+2.2 to +59.4) | 18.4 | 0 | 0 | 6 |
| v3a_r1 | 6 | +941.0% (+921.5 to +981.2) | 93.5 | 0 | 6 | 0 |

## Why this metric, interval and these thresholds

All three were fixed in `docs/gate-revision.md` before any trial here ran, and none is changed
after seeing these results.

- **Geometric-mean TTFT per run.** A run has 34 requests, and requests in a run are not
  independent (closed-loop waves at c=8 share scheduler steps). A run's p95 is its 2nd-3rd
  largest value, set by one or two waves; the geometric mean uses every request. On the
  development A/A data its run-to-run SD (log scale) was 0.056 against 0.112 for p95, so it
  resolves about half the change for the same cost. It compares as a ratio, which matches
  how the regressions Furnace targets act (lost prefix cache, longer context and a bigger model
  scale the whole TTFT distribution) and how a different GPU clock acts.
- **The run as the unit, 90% two-sided Welch interval.** Each run is reduced to one number, so
  the dependence between requests stays inside it and the run-to-run spread already contains
  it. Resampling requests (the replaced bootstrap) treated dependent requests as independent
  and gave intervals about 15% too narrow. Welch is used because base and candidate runs of
  the same repeat were measured to be no more alike than runs of different repeats. A
  two-sided 90% interval is a one-sided 95% statement in each direction: PASS means "a
  regression above 10% is ruled out at 95%", FAIL means "a regression above 10% is
  established at 95%".
- **10% tolerance, 25% block.** These are the plan's policy values, set before any
  measurement as the size of latency change worth stopping a merge for, and kept as they were
  rather than fitted to the noise. On this machine unchanged code moves the geometric mean by
  up to about 13-15% between trials, which is why the decision uses the interval and not the
  point change. A true change near 10% is expected to come out INCONCLUSIVE: that is the
  gate's resolution at 3 runs per side, not something to tune away.

## What this gate does not do

It is a latency-location gate, not a tail-SLO gate. A change confined to the slowest few
percent of requests, with the typical request unchanged, is not detected unless it also
moves the geometric mean. The p95 table above is reported for that reason. It is advisory:
with 3 runs per side its interval is too wide to confirm a 10% tolerance. Not covered: other
GPUs, clocks, models or workloads, concurrency other than 8, and GitHub-hosted runners.

Bookkeeping: verdicts recomputed from the stored raw samples (rounded to 0.01 ms) equal the recorded ones in every trial; interval bounds agree within 0.1 point (rounding).
