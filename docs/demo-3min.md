# Furnace in three minutes

For a technical interviewer or a recorded walkthrough. Part A runs on the laptop alone
(`uv run poe demo-up`, then `uv run python scripts/preflight.py --load`). Part B replaces two
steps with real GitHub **only if** `bench/results/*-live-github/live_run.md` and `verify.md`
exist and passed; otherwise say "the GitHub path is tested against a mock API". Say
"measured on a laptop RTX 3050 Ti at 780 MHz" for every latency. The longer script with
fallbacks is `docs/demo.md`.

Open before starting: `http://localhost:3100/`, the F1 Blueprint (`/scans/<id>` from a fixture
scan), `/guard/r1_dynamic_head` (press **Run Guard** about 2 minutes before 0:50),
`bench/results/2026-10-12-gate-validation/validation/report.md`.

| time | show | say |
|---|---|---|
| 0:00 | Landing hero, press Replay (R1 before/after) | "One harmless-looking PR put a request id and timestamp at the top of the system prompt. On vLLM no two requests share a prefix any more: cache hit 98% to 0%, p95 time to first token about ten times worse." |
| 0:20 | F1 Blueprint, then Graph → click the `/chat` workflow | "Scan is deterministic Python AST and config analysis, no LLM. Every finding cites file and line, and findings are advisory: on five fresh open-source apps half of them were wrong, and I report that. The graph links the route to the handler, the system prompt, the model and the vLLM flags; Guard uses it to pick which checks a diff can affect." |
| 0:50 | `/guard/r1_dynamic_head`, the finished Guard run | "Guard ran only the affected checks. The perf gate renders each revision's own prompts, interleaves the runs on the same GPU and decides on geometric-mean TTFT with a run-level 90% interval: PASS, BLOCK, or INCONCLUSIVE when the noise is too large. Here it BLOCKs." |
| 1:20 | Repair timeline, same page | "Repair writes the regression test first: it must fail on the PR and pass on main. Two rule-based strategies are tried in order. The first keeps the values in the prompt and was rejected in all three trials. The second logs them instead; it was verified in 3 of 3 repeated trials of this one scenario, within +4.2%, +0.9% and +1.7% of main, and it sends byte-identical prompts to main. It is one fixture and one regression family, not a general repair system." |
| 1:55 | `validation/report.md` | "How do I know the gate does not cry wolf? I froze its design before validating it. On 36 unchanged-code trials: zero false failures, 29 passes, 7 inconclusive. The known regression: blocked 6 of 6. And a negative result: regressions I had calibrated at 13 to 30 percent measured only 4 to 7 percent inside the gate, so detection just above the 10 percent tolerance is not shown." |
| 2:30 | `/bench`, the Corrections box | "My own instrument was wrong more than once, including a gate that saw up to 60 percent between identical code; each correction is dated and the old results stay. The optimizer I built recommended keeping the baseline, and its independent rerun was inconclusive, so I don't claim an improvement." |
| 2:50 | Close | "Python only, one GPU, one model, rule-based repair. Every number links to a file, and a human merges every PR." |

## Part B (only after a recorded, passing live GitHub run)

Replace 0:50-1:55 with the demo repository on GitHub: the R1 pull request's **Furnace Guard**
check run, then the draft repair PR into the R1 branch, built on its head commit. Read the
URLs and commit SHAs from `bench/results/<date>-live-github/live_run.md`; say whether the
repair was verified in that live run or refused, as recorded.

## Sources for every number

R1 size: `2026-10-09-gate-warmup-v2/rq5.md`. Gate validation:
`2026-10-12-gate-validation/validation/report.md`, `trials.md`. Repair:
`2026-10-12-gate-validation/rq5.md`, `rq5/prompt_identity.md`. Scanner set 6:
`2026-10-13-set6/NOTES.md`. Optimizer: `2026-10-12-optimizer/NOTES.md`. Corrections:
`2026-10-06/CORRECTIONS.md`.
