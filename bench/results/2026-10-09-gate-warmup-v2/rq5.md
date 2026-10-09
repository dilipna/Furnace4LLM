# RQ5: failing-test-first repair

R1 repaired 3 times end to end, lab vLLM Qwen2.5-0.5B on the laptop GPU, perf gate at concurrency 8 with 3 interleaved runs per revision. Rule strategies tried in order: `move_dynamic_to_suffix`, `move_dynamic_to_log`; the first that passes the tests and the perf budget is proposed. The LLM-patch strategy is not built, so there is no rule-vs-LLM comparison.

| repeat | status | proposed | fails on head / passes on base | regression test | existing tests | PR p95 TTFT vs base | repair p95 TTFT vs base | repair hit rate | audit (full suite on repair) | time (s) |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | verified | `move_dynamic_to_log` | True / True | pass | pass | 87.1 → 890.6 ms (+922.1%, block) | 87.1 → 85.4 ms (-2.0%, pass) | 98% → 98% | success | 196 |
| 1 | verified | `move_dynamic_to_log` | True / True | pass | pass | 82.6 → 912.3 ms (+1004.4%, block) | 82.6 → 89.6 ms (+8.5%, pass) | 98% → 98% | success | 201 |
| 2 | verified | `move_dynamic_to_log` | True / True | pass | pass | 84.0 → 895.7 ms (+965.7%, block) | 84.0 → 88.7 ms (+5.5%, pass) | 98% → 98% | success | 199 |

Success: 3/3 verified repairs; 3/3 audits without a FAIL.

Repeat 0 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (p95 TTFT base 84.8 | PR 910.0 (+972.7%, block) | repair 127.2 (+49.9%, block)); 2. `move_dynamic_to_log` PASS (p95 TTFT base 87.1 | PR 890.6 (+922.1%, block) | repair 85.4 (-2.0%, pass))

Repeat 1 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (p95 TTFT base 84.8 | PR 898.0 (+958.9%, block) | repair 122.2 (+44.1%, block)); 2. `move_dynamic_to_log` PASS (p95 TTFT base 82.6 | PR 912.3 (+1004.4%, block) | repair 89.6 (+8.5%, pass))

Repeat 2 candidates, in order: 1. `move_dynamic_to_suffix` FAIL (p95 TTFT base 88.6 | PR 890.4 (+904.8%, block) | repair 133.2 (+50.3%, block)); 2. `move_dynamic_to_log` PASS (p95 TTFT base 84.0 | PR 895.7 (+965.7%, block) | repair 88.7 (+5.5%, pass))

Repeat 0 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run

Repeat 1 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run

Repeat 2 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run

## r2_context_bloat (attempt)

Status `rejected`. diagnosis: no system message changed from prefix-stable to dynamic-head
