# Furnace in three minutes

For a design-partner call, a technical interviewer, or a recorded walkthrough. Part A runs on
the laptop alone (`uv run poe demo-up`, then `uv run python scripts/preflight.py --load`).
Part B replaces 1:20-1:50 with real GitHub **only if**
`bench/results/*-live-github/live_run.md` and `verify.md` exist and passed; otherwise say
"the GitHub path is tested against a mock GitHub; the live run is next". Say "measured on a
laptop RTX 3050 Ti at 780 MHz" for every latency. The longer script with fallbacks is
`docs/demo.md`.

Open before starting: `http://localhost:3100/` (landing), `/guard/r1_dynamic_head` (press
**Run Guard on this PR** about 2 minutes before 1:20), `/pilot`, and
`bench/results/2026-10-12-gate-validation/validation/report.md`.

| time | show | say |
|---|---|---|
| 0:00 | Landing, first screen | "Furnace is a pre-merge performance check for Python LLM apps that run on their own model server. This is one pull request, recorded, and labeled as recorded." |
| 0:15 | Panel step 1, the diff | "Someone adds a request id and a timestamp to the top of the system prompt, for debugging. The answers don't change, so quality evals pass." |
| 0:30 | Panel steps 2-3 | "But vLLM reuses work across requests that start the same way. Now none do: cache hit 98% to 0%, time to first token about seven times higher. Furnace renders each revision's real prompts with the app's own code, runs main and the PR interleaved on the same GPU, and decides with a 90% interval. Here: BLOCK." |
| 0:55 | Panel step 4, switch trials 1-3 | "Then repair. It writes the regression test first: it must fail on the PR and pass on main. It tries rule-based fixes in order. The first kept the values in the prompt and was rejected by the same gate. The second logs them instead. Across three repeated trials of this one scenario, it cut time to first token by about 86% versus the PR and landed within +4.2%, +0.9% and +1.7% of main. That is one fixture and one regression family, not a general repair system." |
| 1:20 | `/guard/r1_dynamic_head`, the finished live Guard run | "This run happened just now on the laptop runner: only the affected checks ran, and here's the gate's table. Every result is PASS, FAIL, INCONCLUSIVE, or SKIP with a reason. A skipped judge is never counted as passed." |
| 1:50 | `validation/report.md` | "Does the gate cry wolf? I froze its design before validating it. On 36 unchanged-code trials it raised zero false alarms. It blocked the known regression 6 of 6 times. And the honest part: regressions I sized at 13 to 30 percent measured only 4 to 7 percent, and the gate left 15 of 18 undecided. It catches large regressions; small ones near the tolerance are not shown." |
| 2:20 | `/pilot` | "What a pilot needs: a Python app, a model you serve, one GPU machine for the runner, and a GitHub repository. Setup is hands-on today. We write the suite file with you, and the page lists exactly what's supported." |
| 2:45 | Close | "Python only, measured on vLLM, rule-based repair for one regression family, and a human merges every PR. I'm looking for teams that serve their own models and would try it on one repository." |

## Part B (only after a recorded, passing live GitHub run)

Replace 1:20-1:50 with the demo repository on GitHub: the R1 pull request's **Furnace Guard**
check run on its head commit, then the draft repair PR into the R1 branch. Read the URLs and
commit SHAs from `bench/results/<date>-live-github/live_run.md`, and say whether that live
run verified the repair or refused it, as recorded.

## Sources for every number

The landing panel reads `2026-10-12-gate-validation/rq5.json` (per-trial PR vs main, repair
vs main, repair vs PR). "About seven times": the R1 set's median +613% geometric-mean TTFT
(`validation/report.json`, `v3a_r1`). Gate validation: `validation/report.md`, `trials.md`.
Byte-identical prompts: `rq5/prompt_identity.md`. Scanner set 6: `2026-10-13-set6/NOTES.md`.
Optimizer (if asked): `2026-10-12-optimizer/NOTES.md`; keep the baseline, confirmation
inconclusive. Corrections: `2026-10-06/CORRECTIONS.md`.
