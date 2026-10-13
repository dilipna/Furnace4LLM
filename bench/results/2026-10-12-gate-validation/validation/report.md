# Perf-gate validation: fresh trials under the frozen rule

Every trial is the real gate path (prompts rendered from each revision in the sandbox, 3 interleaved runs per side, c=8, 34 requests per run). Rule frozen in `docs/gate-revision.md` (6e90c99; implemented 26fa8eb; sizes for the graded sets fixed in 9d80db8 before any trial). The last column applies the rule that was replaced to the same raw samples. Trials affected by competing work on the machine are left out of the primary row, replaced, and shown again in an 'incl. affected' row (rule: `../NOTES.md`). SM clock across all trials: 780-780 MHz.

| set | true change | trials | PASS | INCONCL. | WARN | BLOCK | FAIL = WARN+BLOCK (exact 95% CI) | measured change, median (range) | interval width, median (pts) | interval contains 0 | old rule on same data: P/I/W/B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1_aa | none (unchanged) | 11/24 | 7 | 4 | 0 | 0 | 0/11 (0%-28%) | -0.3% (-15.0 to +5.4) | 13.0 | 10/11 | 3/8/0/0 |
| v1_aa, incl. affected trials [6, 9, 10] | none (unchanged) | 14/24 | 10 | 4 | 0 | 0 | 0/14 (0%-23%) | -0.0% (-15.0 to +5.4) | 12.4 | 13/14 | 6/8/0/0 |

Unchanged code (V1 + V2 together): false FAIL 0/11 (exact 95% CI 0.0% to 28.5%), PASS 7/11.
The same, including affected trials: false FAIL 0/14 (exact 95% CI 0.0% to 23.2%), PASS 10/14.

Pre-declared targets (primary rows):
- v1_aa: false FAIL 0% (target <= 10%: met), PASS 64% (target >= 70%: NOT met) [partial: 11/24]

## Tail latency (p95), reported separately; advisory, never decides a verdict

Same trials and runs: each run's p95 TTFT, compared with the same run-level 90% Welch interval. 'Ruled out' = interval upper bound <= 10%; 'established' = lower bound > 10%.

| set | trials | p95 change, median (range) | interval width, median (pts) | tail regression > 10% ruled out | established | unresolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v1_aa | 11 | +1.1% (-20.1 to +7.1) | 27.4 | 3 | 0 | 8 |

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
