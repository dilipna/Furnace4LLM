# Perf gate revision: proposal, frozen before implementation (2026-10-12)

Status: **proposal, frozen by the commit that adds this file.** The code change, the
validation driver and the validation results come after it and cannot alter the method or
thresholds below. If validation disappoints, the result is reported as it is.

Why this is being revisited, in the order it happened: the repair loop verified 1 of 3
attempts under the interval gate and the gate returned INCONCLUSIVE for unchanged code in
5/12 (3 runs per side) and 7/8 (5 runs) trials (`2026-10-12-gate-ci/NOTES.md`). Both
results were known before this redesign, so the redesign is *motivated* by them. What
decided its content is only unchanged-code data (A/A) and the statistics of those data;
no repair or regression result was consulted to choose the statistic, the interval or the
run count (`bench/gate_dev_analysis.py` reads A/A files only).

## 1. What the gate has to decide

For a revision R and its base B, run on the same endpoint and prompts: is R's time to
first token worse than B's by more than a stated tolerance? Three answers, never forced:
no (PASS), yes (FAIL), the data cannot say (INCONCLUSIVE). INCONCLUSIVE is a neutral
check that asks for a human, not a pass.

## 2. What is wrong with the current gate

Measured on the development data (20 valid A/A trials, 152 runs of 34 requests; details in
`bench/results/2026-10-12-gate-revision/dev_analysis.md`):

1. **The statistic is a poor choice for 34 requests.** A run's p95 over 34 requests is
   the 2nd-3rd largest value, and 62% of consecutive requests in a run have the same TTFT
   within 3% (closed-loop waves at c=8 share a scheduler step; lag-1 autocorrelation of
   log TTFT 0.33), so a run holds about 4-5 independent-ish waves, not 34 samples. The
   run-level SD of log p95 is 0.112; of the log geometric mean, 0.056.
2. **Resampling requests is the wrong unit.** The request-level layer of the hierarchical
   bootstrap treats dependent requests as independent, and the run-level layer resamples
   3 or 5 units, which has very few distinct resamples. Its 95% interval is about 15%
   narrower than a run-level t interval on the same runs (22.8 vs 26.8 points median
   width): optimistic, in the direction that would produce false alarms.
3. **More requests or pooling does not fix it.** Pooling all requests of all runs gives
   the *worst* tail statistic (SD of the A/A log ratio 0.167 for p95, one trial 102%
   apart, because one slow run sets the pooled tail) and barely helps location statistics.
   Adding requests per run adds waves slowly and does nothing about run-to-run variation
   (the 4x-requests experiment was invalidated by a power loss and is not evidence).
4. **A 10% tolerance cannot be confirmed on p95 at this sample size.** With run-level t
   intervals the median 90% interval for a p95 comparison is 28 points wide at 3 runs and
   18 points at 5; unchanged code would be INCONCLUSIVE in 62-82% of trials. This is a
   property of the metric, not of the number of runs we can afford.

## 3. Proposed method

**Target metric (gate): geometric-mean TTFT** of a run's successful measured requests, and
the quantity compared is the ratio of geometric means (reported as a percent change).
Reasons: it uses every observation; it is a ratio (clock changes act multiplicatively);
the regressions Furnace targets (lost prefix cache, longer context, bigger model) shift the
whole TTFT distribution, which a location statistic detects with about half the run-level
noise of p95. **The p95 is still computed, with its own interval, and reported as
advisory; it does not decide the verdict.** What this gives up, stated plainly: a change
confined to the slowest few percent of requests, with the typical request unchanged, will
not be seen unless it also moves the geometric mean. The gate is therefore a *latency
location* gate, not a tail-SLO gate; the product must not describe it as the latter.

**Resampling / analysis unit: the run.** A run is one benchmark invocation of a revision
(an unmeasured warmup wave, then the measured requests); runs of base and candidate are
interleaved with the order rotated each repeat. Each run is reduced to one number, the
mean of log TTFT. Requests are never resampled: their dependence (waves, shared cache
state) lives inside the run, and the run-to-run variance of the run-level number already
contains the within-run sampling error whatever its dependence structure.

**Run/request dependence, checked.** Between consecutive runs the correlation of the
run-level value is -0.19 (no positive drift carry-over) and the trial-level share of
variance is 0.20; pairing runs by repeat does not reduce variance (SD of paired
differences 0.076 vs 0.065 unpaired). So the two sides are analysed as independent
samples (Welch).

**Interval.** Welch two-sample t interval on the run-level log values, Satterthwaite
degrees of freedom, **two-sided 90% (5% in each tail)**, transformed to a percent change.
Runs per side: **3** (unchanged from today's cost; the development data give 13%
INCONCLUSIVE at 3 and 10% at 4). Fewer than 3 runs per side: no interval is computed and
the verdict is INCONCLUSIVE with the reason. The t quantile is exact
(`guardian/tdist.py`, tested against table values).

**Thresholds (kept from the plan's policy; not tuned):** tolerance `warn_pct = 10%`,
`block_pct = 25%`. The tolerance is *not* a bound on point noise: on the development data
the largest A/A point change of the frozen statistic is 13.0% in magnitude (SD 4.3
points; the old p95 statistic: +13.4%). It is the interval, not the point estimate, that is
meant to keep unchanged code from being called a regression (the largest positive A/A
change is +7.4%); whether it does is what V1/V2 test.

**Decision rules.** With Δ the point change and [L, U] the interval:

| verdict | rule | meaning |
|---|---|---|
| PASS | U ≤ 10% | a regression larger than 10% is ruled out at 95% (one-sided) |
| FAIL (BLOCK) | L > 10% and Δ > 25% | regression beyond tolerance is established, and it is large |
| FAIL (WARN) | L > 10% and Δ ≤ 25% | regression beyond tolerance is established, but modest |
| INCONCLUSIVE | otherwise (the interval straddles 10%) | the data support neither; not a pass |
| ERROR | nothing measured / endpoint down | never a pass |

Plus the existing failure rule: more failed requests than the baseline (by more than one
point of rate) is a FAIL (BLOCK) regardless of latency.
The previous requirement that every candidate run be slower than every base run
("separated") is dropped as a condition (the interval makes it redundant) and kept as a
reported field.

**Repair acceptance (semantics unchanged, statistic and interval replaced).** Accept a
candidate only if (1) it is faster than the PR head with 95% confidence (interval upper
bound < 0) and (2) its worst case against base (interval upper bound) is below the block
threshold; whether it is within the 10% tolerance of base is reported, not assumed.
No acceptance threshold changes.

**Validity rules (declared before running):** a trial is discarded and counted if AC power
was lost during it; a trial in which either side's failed-request rate exceeds 1% is not
discarded: it is a FAIL by the failure rule and is reported. No outlier trimming of any
kind. Every excluded trial is listed with its reason. SM clock and power are recorded per
run and reported; results at different clocks are not pooled without saying so.

## 4. Expected behaviour on the development data (optimistic: the rule was chosen there)

`dev_analysis.md`, geometric mean, 90% interval, tolerance 10%: PASS 87%, INCONCLUSIVE
13%, false FAIL 0% over 92 three-run subsets of 20 trials (the subsets are correlated;
this is not an error-rate estimate). The same rule on p95 would be 18% PASS and 82%
INCONCLUSIVE.

## 5. Validation protocol (fixed now; fresh runs only)

Same machine, vLLM image and model as the development data. On AC power. Each trial is
the real gate path (prompts rendered from each revision's own code in the sandbox, 3
interleaved runs per side, c=8, 34 requests per run).

| set | trials | what it tests | pre-declared target |
|---|---:|---|---|
| V1 fresh unchanged code (A/A) | 24 | false FAIL, PASS rate, INCONCLUSIVE rate | FAIL ≤ 10%, PASS ≥ 70% |
| V2 restored baseline | 12 | R1 applied, then the exact inverse edit plus a comment-only change (bytes differ, behavior identical) vs base | same as V1 |
| V3a R1 dynamic prompt head | 6 | a known large regression (+800% p95 in earlier studies) | BLOCK in all 6 |
| V3b R2 context bloat | 6 | a known regression of unknown size | reported; no target |
| V3c graded context depth | 3 sizes x 6 | detection as a function of true size | reported as a detection-rate table; no claim beyond the sizes tested |
| V4 repair (RQ5), 3 attempts | 3 | the repair loop under the frozen gate | reported as measured; **not** a criterion for the gate |

V3c sizes (`top_k` in the retrieval config) are chosen from a calibration measurement of
raw mean TTFT, not from gate verdicts, and recorded before V3c runs.
Unchanged-code trials V1+V2 give 36; an exact binomial 95% upper bound for the false-FAIL
rate is reported (two-sided Clopper-Pearson; 0/36 would bound it at 9.7%). Targets are reported as met or not met;
nothing is retuned after a miss.

Not covered by this validation, and not to be claimed: other GPUs or clocks, other models,
other workloads, concurrency other than 8, regressions confined to the tail, and any
GitHub-hosted runner.

## 6. Wording that follows from this

Allowed after validation, with the numbers: "A/A-characterized latency-location gate:
geometric-mean TTFT, run-level 90% Welch interval, tolerance 10%". Not allowed: "calibrated",
"p95 gate", "catches regressions" without the sizes tested, "repairs automatically" without
the attempt counts and the conditions (one fixture, one regression family).

## 7. Addendum before V1-V3 ran: graded-regression sizes (2026-10-12)

`bench/gate_validate.py calibrate-topk` measured the raw geometric-mean TTFT effect of
retrieval depth (3 interleaved runs per variant, no gate verdict used):
depth 4 +12.9%, 5 +12.2%, 6 +11.1%, 8 +18.2%, 12 +30.2% vs main
(`bench/results/2026-10-12-gate-validation/validation/calibration_topk.json`; depths 4-6 are
indistinguishable at this precision). V3c therefore uses **depth 4 (about +13%) and depth
8 (about +18%), 6 trials each**; V3b (R2, depth 12 with the budget x4) is the third graded
point (about +30%) and V3a (R1) the large one (about +800%). Only these four sizes are
tested; nothing is said about sizes between or beyond them. Sizes near the 10% tolerance
are expected to come out INCONCLUSIVE; that is a result about the gate's resolution, not
a failure to be tuned away.

## 8. Addendum during V1 (2026-10-13): affected trials

Validity rule added at the owner's direction after V1 trials 1-14 and before trial 15. It
changes neither the statistic, the interval, the run count nor any threshold. A trial during
which competing compute (tests, lint/type checks, builds, Docker/sandbox jobs, benchmarks,
analysis scripts) ran on the machine, as established from a timestamped command log and never
from the trial's result, is kept with its result, left out of the primary tally and replaced
by one extra trial in the same set; the report also shows every figure with it included.
V1 trials 6, 9 and 10 meet it (all three PASS). Rule, evidence and the audit of trials 1-14:
`bench/results/2026-10-12-gate-validation/NOTES.md`.
