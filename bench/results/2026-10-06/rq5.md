# RQ5: failing-test-first repair

R1 repaired 3 times end to end (rule strategy `prefix_stability.move_dynamic_to_suffix`), lab vLLM Qwen2.5-0.5B on the laptop GPU, perf gate at concurrency 8 with 3 interleaved runs per revision. The LLM-patch strategy is not built, so there is no rule-vs-LLM comparison.

| repeat | status | fails on head / passes on base | regression test | existing tests | PR p95 TTFT vs base | repair p95 TTFT vs base | repair hit rate | audit (full suite on repair) | time (s) |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | verified | True / True | pass | pass | 203.1 → 1043.1 ms (+413.7%, block) | 203.1 → 312.9 ms (+54.1%, warn) | 98% → 94% | neutral | 95 |
| 1 | verified | True / True | pass | pass | 231.6 → 1009.9 ms (+336.1%, block) | 231.6 → 269.8 ms (+16.5%, warn) | 98% → 94% | neutral | 94 |
| 2 | verified | True / True | pass | pass | 238.2 → 1071.3 ms (+349.7%, block) | 238.2 → 275.7 ms (+15.7%, warn) | 98% → 94% | neutral | 95 |

Success: 3/3 verified repairs; 3/3 audits without a FAIL.

Repeat 0 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` WARN: median p95 TTFT 259.0 -> 297.1 ms (+14.7%, warn; 3 runs each, runs overlap); prefix-cache hit 98% -> 94%

Repeat 1 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` WARN: median p95 TTFT 240.3 -> 275.6 ms (+14.7%, warn; 3 runs each, runs overlap); prefix-cache hit 98% -> 94%

Repeat 2 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` WARN: median p95 TTFT 254.9 -> 303.0 ms (+18.9%, warn; 3 runs each, runs overlap); prefix-cache hit 98% -> 94%

## r2_context_bloat (attempt)

Status `rejected`. diagnosis: no system message changed from prefix-stable to dynamic-head
