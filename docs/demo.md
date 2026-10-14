# Five-minute demo: reproducible script, sources and fallbacks

Every number on screen comes from the running system or a file in `bench/results/`. Say
"measured on a laptop RTX 3050 Ti" for every latency. The driver picks the GPU clock for this
light load (780 MHz on Oct 6-9 and Oct 12, ~1,960 MHz on Oct 11 after a reboot; never
throttled); pre-flight prints today's clock. Stored results were measured at 780 MHz unless
their folder says otherwise; a run at ~1,960 MHz is 32-48% faster at p95
(`bench/results/2026-10-11-live-clock/`), so compare live dots with stored ticks only at
equal clocks.

The script has two parts. **Part A** runs on the laptop alone and is what can be shown today.
**Part B** (real GitHub) may be shown only after `scripts/live_github_run.py` and
`scripts/live_github_verify.py` have both passed on the demo repository (docs/github-app.md).

## Start (about 5 minutes before)

```bash
uv run poe demo-up                           # Docker, Postgres, lab vLLM, API, scan worker, Guard runner, web build
uv run python scripts/preflight.py --load    # every line OK; "GitHub App" FAILs until part B exists
uv run python scripts/rehearse.py            # optional: the whole part A path in a real browser, ~3.5 min
```

Keep the laptop on AC and the lid open (a sleeping laptop stops Docker and every job). Open
tabs: `http://localhost:3100/`, `/lab`, `/pilot`, `/guard/r1_dynamic_head`, `/bench`.

## Part A (local, 5:00)

| time | show | say, and where the number comes from |
|---|---|---|
| 0:00 | **Landing**: the recorded PR panel; click trials 1-3 | "A PR adds a request id to the top of the system prompt 'for debugging'. Nothing breaks functionally, but no two requests share a prompt prefix any more: prefix-cache hit 98% → 0%, geometric-mean time to first token about seven times higher, BLOCK. The repair logs the values instead: about 86% lower than the PR, within +0.9% to +4.2% of main." Every figure is per trial from `2026-10-12-gate-validation/rq5.json`; the diff is generated from the scenario (`scripts/export_pr_diff.py`). Say it is recorded: the panel says so. |
| 0:30 | **/lab**, the live panel | vLLM's own counters and the GPU's power, clock and temperature, once a second; nothing moves unless the system moved. |
| 0:45 | **Scan** (on `/pilot`): paste `github.com/Azure-Samples/openai-chat-app-quickstart` | The stage log types in with real timings (a few seconds); every Blueprint finding cites file and line. "It reads Python. On apps it had never seen, on its first scan of five unseen apps it found 32 of 48 labeled LLM call sites, and 39 of its 77 findings were right, so findings are advisory." (`2026-10-13-set6/NOTES.md`) |
| 1:30 | **Graph**: click the `POST` workflow | The path traces route → handler → system prompt → model → endpoint → vLLM flags. "This graph is how Guard decides which checks a diff can affect." |
| 1:50 | **/lab → Run it now** (~30 s), and **start step 3:00 in the other tab now** | Each dot is one real request's TTFT against the RQ4 ticks for prefix caching on/off. "Turning prefix caching off raised p95 TTFT by +96% to +433% across all 15 measured cells, same sign in every paired repeat." (`2026-10-06/rq4/rq4.md`) |
| 2:30 | **Queue correlation** (`2026-10-12-correlation/correlation.md`) | "vLLM only queues when concurrency exceeds max-num-seqs; there, time to first token tracks the queue (rho +0.41 with caching on). Below that there is no queue to blame." |
| 3:00 | **/guard/r1_dynamic_head → Run Guard on this PR** (started at 1:50; ~2 min) | The impact graph lights the changed prompt, then what it reaches; each check flips to its verdict. Expected: FAILURE on `prompt_prefix_stable` and the perf gate. "The gate decides on geometric-mean TTFT with an interval across runs; the p95 is shown as advisory, because 34 requests cannot confirm a 10% change in a p95." |
| 3:45 | **Repair timeline** (same page) | The regression test was written first (fails on the PR, passes on main); two rule strategies tried in order; the gate's decision for each. Read the outcome off the page (accepted or refused, with the interval). "It tries its own fixes and refuses the ones it cannot show are faster without a new regression. A human merges; Furnace never pushes to your branches." |
| 4:20 | **/bench → Corrections**, then `docs/gate-revision.md` | "We test our own instrument. Identical code on both sides: the old gate called 5 of 12, and with more runs 7 of 8, such comparisons inconclusive, because its statistic was too noisy. We redesigned it on old data only, froze the design, then validated it on fresh runs, including regressions near the 10% threshold that it is expected not to resolve." Quote only the numbers in the latest `2026-10-12-gate-validation/validation/report.md`. |
| 4:50 | Close | "Every number links to a file. What I did not show is not claimed: real GitHub pull requests, a hosted deploy, TypeScript apps." |

## Part B (real GitHub; only after both live scripts passed)

| show | where | evidence to have open |
|---|---|---|
| Forge draft PR: manifest table, extracted prompt, installed tests | the demo repo's pull requests | `bench/results/<date>-live-github/live_run.md` |
| Furnace Guard check run on the R1 PR, failing, annotated on the prompt hunk | the R1 PR → Checks | `verify.md`: `attribution`, `check_updates` |
| Repair draft PR into the R1 branch, built on its head commit | linked from the R1 PR | `verify.md`: `draft_prs`, `branches_intact` |
| A re-run returns the same PRs; forged webhooks are refused | `live_run.md` replay rows; `verify.md` webhook rows | `verify.md`: `no_duplicates`, `webhook_*` |

## If something fails live

| failure | fallback |
|---|---|
| lab vLLM down or the GPU busy | the live panel switches to "lab offline · showing recorded run" (RQ4 telemetry, labeled with its file); /lab and /guard read stored results |
| Run it now refused (one run at a time, cool-down, rate limit) | the message says why; the last run stays on the chart |
| "No Guard runner is online" | start `uv run poe runner`, or show the last run (it replays from stored events) |
| GitHub scan rate-limited | show the scan of the same repository done earlier (keep its URL) |
| Network down | the local stack, and the screenshots in `docs/demo-shots/` |

## Rehearsal record

**2026-10-14 (UTC), at commit 5806c30**, on the redesigned landing (vLLM, runner, API and the
production web build running): every step passed, no page errors. Landing (recorded PR
panel) then /lab live panel 12.7 s, GitHub scan to Blueprint 5.7 s, graph trace 1.7 s, Run it
now 32.1 s (80/80 requests), Guard run on R1 101.4 s (FAILURE: `prompt_prefix_stable` and the
perf gate), /bench 0.2 s. Screenshots `docs/demo-shots/rehearsal-2026-10-14/`; silent
recording `docs/demo-video/demo-2026-10-13-2357.webm` (local time; git-ignored).

**2026-10-13, at commit baa02a2** (after `poe demo-up`; pre-flight all OK except the GitHub
App, which does not exist yet): every step passed, no page errors. Landing + live panel
8.9 s, GitHub scan to Blueprint 5.1 s, graph trace 1.6 s, Run it now 32.1 s (80/80
requests), Guard run on R1 97.8 s (FAILURE: `prompt_prefix_stable` and the perf gate, BLOCK
at +546.6%, 90% interval +503.1 to +593.2), /bench 0.2 s. Screenshots
`docs/demo-shots/rehearsal-2026-10-13/` and a silent screen recording
`docs/demo-video/demo-2026-10-13-1537.webm` (the video is git-ignored and kept locally; the screenshots are committed). The hero and
product-card copy were narrowed after this rehearsal (text only).

Four browser rehearsals on 2026-10-09 (`docs/demo-shots/rehearsal-1/` … `rehearsal-4/`) passed
every step: scan to Blueprint 3.7-7.2 s, graph trace 1.7-2.5 s, Run it now 27.6-32.5 s, Guard
run to verdict 84-129 s, /bench under 0.5 s. They predate the gate revision and the queue
correlation; rehearse again (`scripts/rehearse.py`) after `poe demo-up` and before showing.
