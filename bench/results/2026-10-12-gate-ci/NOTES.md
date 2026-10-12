# 2026-10-12: repair (RQ5) under the interval rule, and A/A with 5 runs per side

Code `b13cf73` (clean). Lab vLLM, Qwen2.5-0.5B-Instruct, RTX 3050 Ti laptop, on AC at start
(pre-flight 03:48 UTC) and at the end of both runs (manifests: on AC, 80 W limit); SM clock
780 MHz in every run, the same as 2026-10-09 and 2026-10-11. Both drivers check power after
each attempt/trial (none was discarded).

## rq5.md: 1/3 verified (interval acceptance rule)

- Every repeat: the regression test failed on the PR head and passed on base; R1 measured
  +830% to +865% p95 TTFT vs main (BLOCK, intervals entirely above +630%).
- Strategy 1 (move the request id to the end of the user message): rejected 3/3 (point
  +20.7% to +46.7%; twice WARN/BLOCK with the whole interval above the tolerance).
- Strategy 2 (log the request id instead of sending it): point estimate +2.0%, +8.6%, +1.7%
  vs main, prefix-cache hit 98% -> 98%, faster than the PR head every time. Accepted in
  repeat 0 (interval upper bound +12.5%) and **rejected in repeats 1 and 2 because the
  interval's upper bound (+29.7%, +33.3%) was not below the 25% block threshold**. The rule
  refused to accept a candidate it could not bound; the candidate was very likely fine.
- 3/3 full-suite audits of the repaired trees without a FAIL.

Reading: the interval rule does not accept unproven candidates (no false accept), but at 3
runs x 34 requests it lacks the power to confirm a good repair most of the time.
Under the 2026-10-09 point rule the same measurements would have been 3/3 verified.

## gate_noise_r5.md: A/A with 5 interleaved runs per side (8 trials)

0 false WARN or BLOCK; PASS 1/8, INCONCLUSIVE 7/8; the interval contained 0 in 8/8; median
width 27.7 points (3 runs per side on 2026-10-11: 21.4). More runs per side did not narrow
the interval: the statistic (median across runs of each run's p95 over 34 requests) is
itself noisy, so the gate's decision statistic, not the number of runs, is the limit.
