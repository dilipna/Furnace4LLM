# RQ5: failing-test-first repair

R1 repaired 3 times end to end (rule strategy `prefix_stability.move_dynamic_to_suffix`), lab vLLM Qwen2.5-0.5B on the laptop GPU, perf gate at concurrency 8 with 3 interleaved runs per revision. The LLM-patch strategy is not built, so there is no rule-vs-LLM comparison.

| repeat | status | fails on head / passes on base | regression test | existing tests | PR p95 TTFT vs base | repair p95 TTFT vs base | repair hit rate | audit (full suite on repair) | time (s) |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | rejected | True / True | pass | pass | 86.1 → 925.1 ms (+974.1%, block) | 86.1 → 126.9 ms (+47.4%, block) | 98% → 94% | failure (FAIL: bench:chat_perf_gate) | 103 |
| 1 | rejected | True / True | pass | pass | 87.5 → 897.1 ms (+925.1%, block) | 87.5 → 122.3 ms (+39.8%, block) | 98% → 94% | failure (FAIL: bench:chat_perf_gate) | 103 |
| 2 | rejected | True / True | pass | pass | 88.3 → 901.9 ms (+921.4%, block) | 88.3 → 125.4 ms (+42.0%, block) | 98% → 94% | failure (FAIL: bench:chat_perf_gate) | 102 |

Success: 0/3 verified repairs; 0/3 audits without a FAIL.

Repeat 0 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` FAIL: median p95 TTFT 85.8 -> 126.5 ms (+47.5%, block; 3 runs each, runs separated); prefix-cache hit 98% -> 94%

Repeat 1 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` FAIL: median p95 TTFT 83.3 -> 120.4 ms (+44.6%, block; 3 runs each, runs separated); prefix-cache hit 98% -> 94%

Repeat 2 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` FAIL: median p95 TTFT 87.3 -> 126.9 ms (+45.3%, block; 3 runs each, runs separated); prefix-cache hit 98% -> 94%

## r2_context_bloat (attempt)

Status `rejected`. diagnosis: no system message changed from prefix-stable to dynamic-head
