# Case study: catching and repairing a prompt-cache regression, and proving the fix

Furnace is an early-stage tool and a bounded portfolio release. It reads an existing **Python** LLM app,
finds where its inference reliability depends on code (Scan), and on each pull request runs
only the checks the diff can affect, including a serving-performance gate (Guard). For one
supported regression family it writes a failing test first and proposes a rule-based repair
as a draft PR. A human always merges. Everything below was measured on one laptop
(RTX 3050 Ti 4 GB, vLLM, Qwen2.5-0.5B-Instruct, SM clock 780 MHz unless stated) and links
to its raw results.

## The problem

A PR adds a request id and timestamp to the top of the system prompt "for debugging". It is
functionally harmless, but every request now starts with different tokens, so vLLM's prefix
cache never hits: hit rate 98% → 0%, p95 time to first token **+905% to +1,004%**
([2026-10-09-gate-warmup-v2/rq5.md](../bench/results/2026-10-09-gate-warmup-v2/rq5.md)).

## The hard part was the gate, not the detection

A latency gate that runs on a laptop must not call unchanged code a regression. My first
three gates did, or could not tell:

1. An A/A test (identical revisions) found up to 60% apart: the first wave after idle set
   the p95. A warmup wave fixed it and the earlier result was withdrawn in a dated
   correction ([2026-10-06/CORRECTIONS.md](../bench/results/2026-10-06/CORRECTIONS.md)).
2. A p95 over 34 requests is nearly the maximum, and requests in a closed-loop run arrive in
   dependent waves, so a request-level bootstrap was ~15% too narrow.
3. The fix was chosen on old A/A data only and **frozen before any code or validation**
   ([gate-revision.md](gate-revision.md), commit 6e90c99): geometric-mean TTFT per run, the
   run as the unit, a 90% Welch interval, the plan's unchanged 10% / 25% thresholds; p95 is
   reported but does not decide.

Fresh validation with the rule unchanged
([report](../bench/results/2026-10-12-gate-validation/validation/report.md), [every trial](../bench/results/2026-10-12-gate-validation/validation/trials.md),
[notes](../bench/results/2026-10-12-gate-validation/NOTES.md)): 63 trials (60 counted, 3
affected by other work on the machine, kept and replaced), all on AC at 780-828 MHz.

| what | result |
|---|---|
| unchanged code, 36 trials (24 fresh A/A + 12 restored baseline, both planned up front) | **0 false FAIL** (exact 95% CI 0-9.7%), 29 PASS, 7 INCONCLUSIVE |
| R1, the regression above | **BLOCK 6/6** (+609% to +621%) |
| graded regressions calibrated at +13%, +18%, +30% | measured only +4% to +7% inside the gate: INCONCLUSIVE 15/18, PASS 3/18. **Detection just above the 10% tolerance is not shown** |

## Repair, verified by the same gate

The loop writes a regression test that must fail on the PR and pass on main, then tries two
deterministic strategies in order and accepts one only if the gate shows it faster than the
PR (the upper bound of its 90% interval below 0%, a 95% one-sided limit) and bounded below +25% against main.

Under the frozen gate: **3 of 3 repeated verification trials of this one scenario**
(fixture F1, regression R1) verified ([rq5.md](../bench/results/2026-10-12-gate-validation/rq5.md)).
The first strategy (keep the values, move them to the end of the prompt) was rejected every
time (INCONCLUSIVE once, BLOCK at +38% and +40%). The second (log the values instead of
sending them) passed at +4.2%, +0.9% and +1.7% vs main (90% upper bounds +9.5%, +4.1%, +7.2%)
and -85.5%, -85.6%, -86.0% vs the PR, restored the 98% cache hit, and
renders byte-identical prompts to main for 34/34 questions
([prompt_identity.md](../bench/results/2026-10-12-gate-validation/rq5/prompt_identity.md)). The logged values are a
random id and a timestamp; the repair PR tells the reviewer that Furnace does not inspect
logged values for user or secret data. A context-bloat regression (R2) is refused as
unsupported. Under the previous gate the same loop verified 1/3 and refused a good fix twice
as unproven ([2026-10-12-gate-ci/rq5.md](../bench/results/2026-10-12-gate-ci/rq5.md)); that
result is what motivated the gate revision and is reported, not replaced.

## Other results, including the unflattering ones

- **Scanner** on apps it never saw, labels committed before the scan: first-scan call-site
  recall 4/34 over sets 1-5; on set 6, call sites 32/48 (all 32 correct) but Blueprint
  finding precision **39/77**, while 148/148 evidence links resolved. Findings are advisory;
  the rule behind 28 of the 38 false findings is now experimental and kept out of the default
  list ([set 6 notes](../bench/results/2026-10-13-set6/NOTES.md)).
- **Prefix caching** off raised p95 TTFT in all 15 measured cells (+193% to +433% at
  max-num-seqs 32) ([rq4.md](../bench/results/2026-10-06/rq4/rq4.md)).
- **Optimizer** (8 serving configs, quality-constrained, rules fixed first): keep the
  baseline; the best config's independent rerun was inconclusive (goodput +3.8%, 90% CI
  -8.8 to +18.2) ([notes](../bench/results/2026-10-12-optimizer/NOTES.md)).
- **Kernel Lab**: a Triton RMSNorm first looked 9x faster than `torch.compile`; the baseline
  had silently fallen back to eager. Fixed, they are at parity (36/36 correct)
  ([results](../kernel_lab/results/2026-10-09/)).

## Limits

One GPU, one small model, one workload; the driver picks the clock (780 MHz here, ~1,960 MHz
after one reboot), so only equal-clock results are compared. One repairable regression
family, rule-based. Python only. The LLM judge is built but uncalibrated (no labels) and
decides nothing. Labels for held-out sets were written by the developer agent. The GitHub
App path is tested against a mock GitHub; a live run is claimed only if
`bench/results/*-live-github/` exists. The production API image passed a local smoke test
(`scripts/smoke_hosted.py`); it is not deployed. Verification levels are kept apart:
local (verified), real GitHub (pending), hosted (not deployed).
