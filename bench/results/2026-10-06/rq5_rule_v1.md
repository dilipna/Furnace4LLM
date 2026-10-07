# RQ5: failing-test-first repair

R1 repaired 3 times end to end (rule strategy `prefix_stability.move_dynamic_to_suffix`), lab vLLM Qwen2.5-0.5B on the laptop GPU, perf gate at concurrency 8 with 3 interleaved runs per revision. The LLM-patch strategy is not built, so there is no rule-vs-LLM comparison.

| repeat | status | fails on head / passes on base | regression test | existing tests | PR p95 TTFT vs base | repair p95 TTFT vs base | repair hit rate | audit (full suite on repair) | time (s) |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | rejected | True / True | pass | pass | 244.1 → 1100.2 ms (+350.6%, block) | 244.1 → 436.4 ms (+78.7%, block) | 98% → 83% | failure (FAIL: bench:chat_perf_gate) | 97 |
| 1 | rejected | True / True | pass | pass | 257.0 → 1076.5 ms (+318.9%, block) | 257.0 → 445.2 ms (+73.2%, block) | 98% → 83% | failure (FAIL: bench:chat_perf_gate) | 96 |
| 2 | verified | True / True | pass | pass | 235.1 → 1052.2 ms (+347.5%, block) | 235.1 → 437.9 ms (+86.2%, warn) | 98% → 83% | failure (FAIL: bench:chat_perf_gate) | 95 |

Success: 1/3 verified repairs; 0/3 audits without a FAIL.

Repeat 0 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` FAIL: median p95 TTFT 219.1 -> 449.3 ms (+105.1%, block; 3 runs each, runs separated); prefix-cache hit 98% -> 83%

Repeat 1 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` FAIL: median p95 TTFT 221.7 -> 435.0 ms (+96.2%, block; 3 runs each, runs separated); prefix-cache hit 98% -> 83%

Repeat 2 audit, items not PASS: `judge:ungrounded_answer` SKIP: no judge model key configured (BYOK); judge not run; `bench:chat_perf_gate` FAIL: median p95 TTFT 239.7 -> 445.5 ms (+85.9%, block; 3 runs each, runs separated); prefix-cache hit 98% -> 83%

## r2_context_bloat (attempt)

Status `rejected`. diagnosis: no system message changed from prefix-stable to dynamic-head
