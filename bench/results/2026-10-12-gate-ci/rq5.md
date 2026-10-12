# RQ5: failing-test-first repair

R1 repaired 3 times end to end, lab vLLM Qwen2.5-0.5B on the laptop GPU, perf gate at concurrency 8 with 3 interleaved runs per revision. Rule strategies tried in order: `move_dynamic_to_suffix`, `move_dynamic_to_log`; the first that passes the tests and the perf budget is proposed. The LLM-patch strategy is not built, so there is no rule-vs-LLM comparison.

| repeat | status | proposed | fails on head / passes on base | regression test | existing tests | PR p95 TTFT vs base | repair p95 TTFT vs base | repair hit rate | audit (full suite on repair) | time (s) |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | verified | `move_dynamic_to_log` | True / True | pass | pass | 97.3 → 907.6 ms (+833.2%, block) | 97.3 → 99.2 ms (+2.0%, inconclusive) | 98% → 98% | neutral | 214 |
| 1 | rejected | – | True / True | pass | pass | 100.2 → 931.9 ms (+830.0%, block) | 100.2 → 108.8 ms (+8.6%, inconclusive) | 98% → 98% | neutral | 212 |
| 2 | rejected | – | True / True | pass | pass | 97.1 → 937.0 ms (+865.4%, block) | 97.1 → 98.7 ms (+1.7%, inconclusive) | 98% → 98% | success | 213 |

Success: 1/3 verified repairs; 3/3 audits without a FAIL.

Repeat 0 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (p95 TTFT base 108.0 | PR 108.0 -> 930.6 ms (+761.6%, 95% CI +330.1% to +843.4%; BLOCK at tolerance 10%) | repair 108.0 -> 154.1 ms (+42.6%, 95% CI -23.8% to +50.4%; INCONCLUSIVE at tolerance 10%)); 2. `move_dynamic_to_log` PASS (p95 TTFT base 97.3 | PR 97.3 -> 907.6 ms (+833.2%, 95% CI +734.6% to +966.5%; BLOCK at tolerance 10%) | repair 97.3 -> 99.2 ms (+2.0%, 95% CI -4.2% to +12.5%; INCONCLUSIVE at tolerance 10%))

Repeat 1 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (p95 TTFT base 97.4 | PR 97.4 -> 919.4 ms (+844.0%, 95% CI +699.5% to +984.9%; BLOCK at tolerance 10%) | repair 97.4 -> 142.8 ms (+46.7%, 95% CI +25.8% to +71.4%; BLOCK at tolerance 10%)); 2. `move_dynamic_to_log` FAIL (p95 TTFT base 100.2 | PR 100.2 -> 931.9 ms (+830.0%, 95% CI +632.4% to +941.0%; BLOCK at tolerance 10%) | repair 100.2 -> 108.8 ms (+8.6%, 95% CI -18.6% to +29.7%; INCONCLUSIVE at tolerance 10%))

Repeat 2 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (p95 TTFT base 106.7 | PR 106.7 -> 923.8 ms (+765.8%, 95% CI +640.1% to +896.9%; BLOCK at tolerance 10%) | repair 106.7 -> 128.8 ms (+20.7%, 95% CI +16.6% to +44.1%; WARN at tolerance 10%)); 2. `move_dynamic_to_log` FAIL (p95 TTFT base 97.1 | PR 97.1 -> 937.0 ms (+865.4%, 95% CI +703.5% to +1050.1%; BLOCK at tolerance 10%) | repair 97.1 -> 98.7 ms (+1.7%, 95% CI -13.1% to +33.3%; INCONCLUSIVE at tolerance 10%))

Repeat 0 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` WARN: median p95 TTFT 98.9 -> 98.9 ms (+0.1%, 95% CI -17.2% to +11.8%; INCONCLUSIVE at tolerance 10%); 3 runs each, runs overlap; prefix-cache hit 98% -> 98

Repeat 1 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` WARN: median p95 TTFT 96.5 -> 102.4 ms (+6.1%, 95% CI -6.0% to +16.2%; INCONCLUSIVE at tolerance 10%); 3 runs each, runs overlap; prefix-cache hit 98% -> 98

Repeat 2 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run

## r2_context_bloat (attempt)

Status `rejected`. diagnosis: no system message changed from prefix-stable to dynamic-head
