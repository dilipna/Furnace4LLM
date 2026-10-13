# Furnace in 90 seconds

For a technical interviewer or a booth. Everything shown runs locally (`uv run poe demo-up`)
or is a file in `bench/results/`. The full 5-minute script with fallbacks is `docs/demo.md`.

| time | show | say |
|---|---|---|
| 0:00 | Landing hero (R1 replay) | "One innocent-looking PR, a request id added to the top of the system prompt, made this app's p95 time-to-first-token about 10x worse on vLLM, because no two requests share a prompt prefix any more: prefix-cache hit rate went from 98% to 0%." |
| 0:15 | Blueprint of `furnace-demo-f1`, then the graph path trace | "Scan is deterministic: AST and config analysis, no LLM. Every finding cites file and line. The graph links the endpoint to the handler, the system prompt, the model and the vLLM flags; that is what Guard uses to pick checks." |
| 0:30 | `/guard/r1_dynamic_head`, press **Run Guard** (pre-started) | "Guard runs only what the diff can affect. The perf gate benchmarks the prompts each revision's own code renders, interleaved, on the same GPU, and decides on the geometric-mean time to first token with a run-level interval: PASS, BLOCK, or INCONCLUSIVE when the noise is too large, never a fake pass. The p95 is shown, but 34 requests are too few to decide on it." |
| 0:50 | Repair timeline, same page | "Repair is not free-form generation: the regression test is written first and must fail on the PR and pass on main; deterministic strategies are tried in order; a candidate must be shown faster than the PR and bounded against main. Its first candidate failed its own gate in 3/3 attempts. Under the previous gate rule it verified the good fix in 1/3 and refused it twice as unproven; that is why the gate's statistic was redesigned, and repair under the new rule is reported as measured, not assumed." |
| 1:10 | `/bench`, the Corrections box | "The evidence includes my mistakes: the gate was once biased (an A/A test found up to 60% between identical revisions); a newer A/A found the 9.7% noise bound too optimistic; later I found the gate's own statistic too noisy and redesigned it, freezing the design before validating it on fresh runs. Negative results stay in the report." |
| 1:25 | Close | "Everything opens a draft PR; a human merges." |

If the GitHub App is installed (docs/github-app.md), replace 0:30-1:10 with the real PR: the
Furnace Guard check run on the R1 PR and the draft repair PR it opened. Say which one you are
showing: the GitHub path has a recorded live run only if `bench/results/*/live-github*` exists.

Numbers to have ready (sources): R1 +905% to +1,004% p95 TTFT, hit 98% → 0%
(`2026-10-09-gate-warmup-v2/rq5.md`); revised gate, fresh validation (in progress, check
the latest `2026-10-12-gate-validation/validation/report.md` before quoting); Scan on apps it
had never seen: 4/34 labeled call sites on first scan, all 4 predictions right
(`2026-10-12-reconcile/scanner_reconciliation.md`). Say "measured on a laptop RTX 3050 Ti at
780 MHz" for every latency.
