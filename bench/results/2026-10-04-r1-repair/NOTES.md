# R1 end-to-end repair with a real performance gate (2026-10-04)

**Scenario.** `fixtures/scenarios/f1_scenarios.py::r1_dynamic_head`: a PR prepends
`f"Request {uuid.uuid4().hex[:8]} at {datetime.now(UTC).isoformat()}\n"` to F1's system prompt.

**What ran** (`furnace.guardian.repair.loop.repair_prefix_instability`, total ~38 s):

1. Harness generated from F1's own `/chat` handler (`furnace_harness.py`).
2. Regression test written first, calibrated on the base revision (two different requests
   share 3,954 leading characters on base; 15 on the PR head; threshold 3,558).
3. Reproduced in the Docker sandbox: the test FAILS on the PR head and PASSES on base.
4. Localized to 2 hunks in `app/prompts.py::build_messages`.
5. Candidate from the deterministic rule `prefix_stability.move_dynamic_to_suffix`
   (keeps the request id and timestamp, moves them after the static text).
6. Validated in the sandbox: regression test passes, existing tests pass.
7. Performance gate: prompts rendered from each revision's own code (34 unique questions,
   unique per-run reference appended so no request repeats), replayed by furnace-bench at
   concurrency 8, 64 output tokens, against vLLM 0.30.0 serving Qwen2.5-1.5B-Instruct-AWQ on
   an RTX 3050 Ti Laptop GPU.

| revision | TTFT p95 | vs base | prefix-cache hit | SLO goodput (TTFT ≤ 500 ms) |
|---|---:|---:|---:|---:|
| base | 579.3 ms | – | 96.1% | 6.25 req/s |
| PR head | 1,472.7 ms | +154.2% (block) | 0.0% | 0.93 req/s |
| repair | 647.5 ms | +11.8% (warn) | 80.8% | 5.64 req/s |

Policy: warn above +10%, block above +25% (p95 TTFT vs base).

**Residual.** The repair keeps the per-request id inside the system message (at its end), which
still prevents sharing of the retrieved-context block that follows it; hence 80.8% vs 96.1% hits
and +11.8% p95. Moving the dynamic values to the end of the *user* message would remove this, at
the cost of a larger change to the PR's intent. Not implemented yet.

**Caveats.** One run per revision, n = 34 at a single concurrency level. FurnaceBench RQ5 will
repeat this with 3 repetitions and report spread.

Artifacts: `repair.patch` (fix + harness + regression test), `attempt.json` (RepairAttempt),
`perf.json` (gate verdicts and full furnace-bench reports for all three revisions).
