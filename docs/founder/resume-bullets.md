# Resume bullets for Furnace (2026-10-14)

Two variants, two bullets each, written to match the style of the current resume
(`Dilip_Nallamasa_Resume_Tsenta_2026-10-12.pdf`: result first, numbers with their
denominators). Every number traces to `docs/claims.md`. Furnace is a solo project with no
users or customers yet; nothing here implies otherwise.

Project line for both: **Furnace** | github.com/dilipna/Furnace4LLM (add the site URL only
after it is deployed)

## A. Inference and ML infrastructure

- Built a pre-merge latency gate for LLM apps on vLLM: replays each revision's real prompts
  interleaved on one GPU and decides on geometric-mean TTFT with a run-level 90% interval;
  froze the design before validating it: 0/36 false alarms, prompt-cache regression blocked 6/6.
- Wrote a streaming load generator (TTFT/TPOT, goodput, CIs, NVML and vLLM metrics): turning
  prefix caching off raised p95 TTFT by 193-433%; reported that the gate left 15/18 small
  regressions undecided instead of retuning it.

## B. Applied AI and forward-deployed engineering

- Built a GitHub check for LLM serving performance end to end (FastAPI, Postgres job queue
  with leases, Docker sandbox, GitHub App webhooks, check runs, draft PRs); it ran 46% of
  checks and reached the full suite's verdict on 13/13 scripted PRs.
- Shipped failing-test-first repair for one regression family: a draft PR opens only after
  the new test, the suite and the perf gate pass; verified in 3/3 trials (TTFT 86% below the
  PR, within 4.2% of main); wrote pilot onboarding that states every limit.

## Sources and what to say if asked

| phrase | source | say in an interview |
|---|---|---|
| 0/36 false alarms; blocked 6/6 | `bench/results/2026-10-12-gate-validation/validation/report.md` | 36 unchanged-code trials (PASS 29, INCONCLUSIVE 7); design frozen in `docs/gate-revision.md` before any trial; 3 affected trials replaced as planned (63 recorded) |
| 15/18 undecided | same report, graded sets | regressions sized at +13 to +30% measured +4 to +7% in the gate; detection near the 10% tolerance is not shown |
| 193-433% | `bench/results/2026-10-06/rq4/rq4.md` | max-num-seqs 32, every cell, same sign in every paired repeat, laptop RTX 3050 Ti at 780 MHz, Qwen2.5-0.5B |
| 46%; 13/13 | `bench/results/2026-10-06/rq3.md` | 13 scripted PRs on fixture F1, under the gate of that date (a p95 point rule later found biased); the selection does not depend on the gate, the perf verdicts do |
| 3/3; 86% below the PR; within 4.2% of main | `bench/results/2026-10-12-gate-validation/rq5.md` | three repeated trials of **one** scenario (fixture F1, regression R1), not a rate over apps; the first strategy was rejected by the same gate; repaired prompts byte-identical to main for 34/34 questions |
| GitHub App, check runs, draft PRs | `docs/github-app.md`, `docs/security.md` | tested against a mock GitHub with 390+ tests; **the live run on a real repository is pending** (say so if asked, and update this line after `live_run.md` exists) |

## Do not write

- "customers", "users", "pilots", "startup raised", "investor": none has happened.
- "auto-repair" or "fixes regressions" without "one regression family".
- "production-ready", "deployed" (until a hosted URL exists and is checked).
- Scanner precision as a strength: 39/77 findings were right on unseen apps (judged by the
  developer); it is a limit, not a headline.
- That a portfolio project equals production experience; the PwC and Globant lines carry
  that.

## Which gaps these fill (from the current resume)

The resume already shows RAG, agents, guardrails, a T4 vLLM benchmark, FastAPI, Docker and
Postgres. Furnace adds what it does not show yet: statistical decision rules for latency
with a pre-registered validation, prefix-cache behavior, a durable job queue (leases,
fencing, timeouts), sandboxed execution of untrusted code, and a GitHub App integration
(webhook HMAC, idempotent check runs and draft PRs).
