# Furnace in three minutes (narration script)

For a founder conversation, a design-partner call, a technical interviewer, or a narrated
recording. Part A works with only the laptop (`uv run poe demo-up`, then
`uv run python scripts/preflight.py --load`). Part B replaces 1:20-1:50 with the recorded real-GitHub run (it exists and passed:
`bench/results/2026-10-14-live-github/`).
Say "measured on a laptop RTX 3050 Ti" for every latency. No laptop? Use the hosted site or the
recording on `/demo` and skip 1:20 (the live run). The longer script with fallbacks is
`docs/demo.md`.

Open before starting: `/` (landing), `/demo`, `/guard/r1_dynamic_head` (press **Run Guard on
this PR** about 2 minutes before 1:20), `/pilot`.

| time | show | say |
|---|---|---|
| 0:00 | Landing, first screen | "Furnace is a performance check for pull requests in Python LLM apps that run on their own model server. It catches the change that makes responses slower before it merges, and drafts a tested fix. What you're seeing is a recorded run, and it's labeled that way." |
| 0:20 | `/demo`, the walkthrough: step 1, the diff | "A developer adds a request ID and a timestamp to the top of the system prompt, for debugging. The answers don't change, so answer-quality checks pass." |
| 0:35 | Steps 2-3 | "But vLLM reuses work across requests that start with the same text. Now none do: cache reuse goes from 98% to 0%, and time to first token is about seven times higher. Furnace renders each revision's real prompts with the app's own code, runs main and the PR interleaved on the same GPU, and decides with a 90% interval. Here it blocks the PR." |
| 0:55 | Step 4, switch trials 1-3 | "Then it repairs. First it writes a regression test that must fail on the PR and pass on main. Then it tries rule-based fixes in order. The first kept the values in the prompt, and the same gate rejected it. The second logs them instead. Across three repeated trials of this one scenario, it cut time to first token by about 86% versus the PR and landed within 4.2% of main. That's one fixture and one regression family, not a general repair system." |
| 1:20 | `/guard/r1_dynamic_head`, the finished live Guard run | "This run happened just now on my laptop runner. Only the affected checks ran, and every result is PASS, FAIL, INCONCLUSIVE, or SKIP with a reason. A skipped check is never counted as passed." |
| 1:50 | Landing, Evidence row (or `validation/report.md`) | "Does the gate cry wolf? I froze its design before validating it. On 36 unchanged-code trials it raised zero false alarms, and it blocked the known regression 6 of 6 times. The honest part: smaller slowdowns were left undecided in 15 of 18 trials, so catching regressions just above the 10% tolerance isn't shown yet." |
| 2:20 | `/pilot` | "A pilot needs a Python app, a model you serve, one GPU machine for the runner, and a GitHub repository. Setup is hands-on today: I write the configuration with you in one session." |
| 2:45 | Close | "It's Python only, measured on vLLM, with rule-based repair for one regression family, and a person merges every PR. I'm looking for a few teams that serve their own models to try it on one repository." |

## Part B (only after a recorded, passing live GitHub run)

Replace 1:20-1:50 with the demo repository on GitHub, or the "On real GitHub" section of
`/demo`: https://github.com/dilipna/furnace-demo-f1/pull/2 (the regression; open the
**Furnace Guard** check: failure, annotations on `app/prompts.py`), then
https://github.com/dilipna/furnace-demo-f1/pull/3 (the draft fix into the PR's branch). Say:
"This ran on real GitHub on October 14. The check landed on the PR's exact commit; the fix
measured 1.6% faster than main and was opened as a draft; an independent check of GitHub
passed 10 of 10. The first attempt failed because GitHub requires a special permission to
write CI files. I chose not to request it, so Furnace leaves that file for the reviewer."

## Sources for every number

The landing hero and `/demo` read `2026-10-12-gate-validation/rq5.json` (per trial: PR vs
main, repair vs main, repair vs PR, cache hit rates). "About seven times": 494 / 69 ms in
trial 1, and the R1 validation set's median +613% geometric-mean TTFT
(`validation/report.json`, `v3a_r1`). 0/36, 6/6, 15/18: `validation/report.json` (sets V1+V2,
V3a, V3b+V3c). Byte-identical prompts: `rq5/prompt_identity.md`. Optimizer (if asked):
`2026-10-12-optimizer/NOTES.md`; keep the baseline, confirmation inconclusive. Corrections:
`2026-10-06/CORRECTIONS.md`.
