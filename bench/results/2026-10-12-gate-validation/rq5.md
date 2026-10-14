# RQ5: failing-test-first repair

R1 repaired 3 times end to end, lab vLLM Qwen2.5-0.5B on the laptop GPU, perf gate at concurrency 8 with 3 interleaved runs per revision. Rule strategies tried in order: `move_dynamic_to_suffix`, `move_dynamic_to_log`; the first that passes the tests and the perf budget is proposed. The LLM-patch strategy is not built, so there is no rule-vs-LLM comparison.

| repeat | status | proposed | fails on head / passes on base | regression test | existing tests | PR geometric-mean TTFT vs base | repair geometric-mean TTFT vs base | repair geometric-mean TTFT vs PR | repair hit rate | audit (full suite on repair) | time (s) |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | verified | `move_dynamic_to_log` | True / True | pass | pass | 68.6 → 494.2 ms (+620.7%, interval +590.3% to +652.5%, block) | 68.6 → 71.5 ms (+4.2%, interval -0.8% to +9.5%, pass) | 494.2 → 71.5 ms (-85.5%, interval -86.2% to -84.9%, pass) | 98% → 98% | success | 203 |
| 1 | verified | `move_dynamic_to_log` | True / True | pass | pass | 70.5 → 494.7 ms (+601.8%, interval +577.9% to +626.5%, block) | 70.5 → 71.1 ms (+0.9%, interval -2.2% to +4.1%, pass) | 494.7 → 71.1 ms (-85.6%, interval -86.0% to -85.2%, pass) | 98% → 98% | success | 197 |
| 2 | verified | `move_dynamic_to_log` | True / True | pass | pass | 69.1 → 501.6 ms (+626.1%, interval +608.8% to +643.8%, block) | 69.1 → 70.2 ms (+1.7%, interval -3.6% to +7.2%, pass) | 501.6 → 70.2 ms (-86.0%, interval -86.7% to -85.2%, pass) | 98% → 98% | success | 196 |

Success: 3/3 verified repairs; 3/3 audits without a FAIL.

Acceptance rule (`perf_gate.accept_repair`): the repair must be faster than the PR (upper bound of the 90% interval vs the PR below 0%) and its worst case vs base (upper bound vs base) must stay below the 25% block threshold; being inside the 10% tolerance of base is reported, not required. These are repeated trials of one scenario (fixture F1, regression R1), not a rate over apps or regression types. A SKIP in the audit is not a pass: the judge did not run.

Repeat 0 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (geometric-mean TTFT base 91.0 | PR 91.0 -> 498.4 ms (+448.0%, 90% interval +270.0% to +711.7%; BLOCK at tolerance 10%) | repair 91.0 -> 99.6 ms (+9.5%, 90% interval -26.0% to +62.1%; INCONCLUSIVE at tolerance 10%)); 2. `move_dynamic_to_log` PASS (geometric-mean TTFT base 68.6 | PR 68.6 -> 494.2 ms (+620.7%, 90% interval +590.3% to +652.5%; BLOCK at tolerance 10%) | repair 68.6 -> 71.5 ms (+4.2%, 90% interval -0.8% to +9.5%; PASS at tolerance 10%))

Repeat 1 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (geometric-mean TTFT base 71.3 | PR 71.3 -> 501.7 ms (+603.5%, 90% interval +556.3% to +654.0%; BLOCK at tolerance 10%) | repair 71.3 -> 98.3 ms (+37.8%, 90% interval +28.6% to +47.6%; BLOCK at tolerance 10%)); 2. `move_dynamic_to_log` PASS (geometric-mean TTFT base 70.5 | PR 70.5 -> 494.7 ms (+601.8%, 90% interval +577.9% to +626.5%; BLOCK at tolerance 10%) | repair 70.5 -> 71.1 ms (+0.9%, 90% interval -2.2% to +4.1%; PASS at tolerance 10%))

Repeat 2 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (geometric-mean TTFT base 70.7 | PR 70.7 -> 502.7 ms (+610.8%, 90% interval +597.8% to +624.1%; BLOCK at tolerance 10%) | repair 70.7 -> 98.7 ms (+39.6%, 90% interval +33.7% to +45.8%; BLOCK at tolerance 10%)); 2. `move_dynamic_to_log` PASS (geometric-mean TTFT base 69.1 | PR 69.1 -> 501.6 ms (+626.1%, 90% interval +608.8% to +643.8%; BLOCK at tolerance 10%) | repair 69.1 -> 70.2 ms (+1.7%, 90% interval -3.6% to +7.2%; PASS at tolerance 10%))

Repeat 0 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run

Repeat 1 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run

Repeat 2 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run

## r2_context_bloat (attempt)

Status `rejected`. diagnosis: no system message changed from prefix-stable to dynamic-head
