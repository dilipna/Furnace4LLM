# Furnace in 90 seconds

For a technical interviewer or a booth. Everything shown runs locally (`uv run poe demo-up`)
or is a file in `bench/results/`. The full 5-minute script with fallbacks is `docs/demo.md`.

| time | show | say |
|---|---|---|
| 0:00 | Landing hero (R1 replay) | "One innocent-looking PR, a request id added to the top of the system prompt, made this app's p95 time-to-first-token about 10x worse on vLLM, because no two requests share a prompt prefix any more: prefix-cache hit rate went from 98% to 0%." |
| 0:15 | Blueprint of `furnace-demo-f1`, then the graph path trace | "Scan is deterministic: AST and config analysis, no LLM. Every finding cites file and line. The graph links the endpoint to the handler, the system prompt, the model and the vLLM flags; that is what Guard uses to pick checks." |
| 0:30 | `/guard/r1_dynamic_head`, press **Run Guard** (pre-started) | "Guard runs only what the diff can affect. The perf gate benchmarks the prompts each revision's own code renders, interleaved, on the same GPU, and decides with a 95% interval: PASS, BLOCK, or INCONCLUSIVE when the noise is too large, never a fake pass." |
| 0:50 | Repair timeline, same page | "Repair is not free-form generation: the regression test is written first and must fail on the PR and pass on main; deterministic strategies are tried in order; a candidate must be faster than the PR with 95% confidence and bounded against main. Its first candidate failed its own gate in 3/3 attempts. Under the stricter interval rule it verified the good fix in 1/3; twice it refused it as unproven: noisy measurements are not allowed to approve a change." |
| 1:10 | `/bench`, the Corrections box | "The evidence includes my mistakes: the gate was once biased (an A/A test found up to 60% between identical revisions); a newer A/A found the 9.7% noise bound too optimistic, which is why the gate now uses intervals. Negative results stay in the report." |
| 1:25 | Close | "Everything opens a draft PR; a human merges." |

If the GitHub App is installed (docs/github-app.md), replace 0:30-1:10 with the real PR: the
Furnace Guard check run on the R1 PR and the draft repair PR it opened. Say which one you are
showing: the GitHub path has a recorded live run only if `bench/results/*/live-github*` exists.

Numbers to have ready (sources): R1 +905% to +1,004% p95 TTFT, hit 98% → 0%
(`2026-10-09-gate-warmup-v2/rq5.md`); A/A at 3 × 34 requests: 0/12 false WARN or BLOCK,
5/12 INCONCLUSIVE, interval covers 0 in 12/12 (`2026-10-11-gate-ci/gate_noise.md`); Scan
held-out set 3: 8/9 call sites at precision 1.00 (`2026-10-09/rq1.md`). Say "measured on a
laptop RTX 3050 Ti at 780 MHz" for every latency.
