# Resume bullets for Furnace (2026-10-14)

Two final bullets, written to match the style of the current resume
(`Dilip_Nallamasa_Resume_Tsenta_2026-10-12.pdf`: result first, numbers with their
denominators). Every number traces to `docs/claims.md`. Furnace is a solo project with no
users or customers yet; nothing here implies otherwise.

Project line: **Furnace** | github.com/dilipna/Furnace4LLM | furnace-5h6.pages.dev

## Final bullets (2026-10-15)

- Built Furnace, a pre-merge latency check for LLM apps served on vLLM: it replays each pull
  request's real prompts interleaved with main on one GPU and decides on geometric-mean TTFT
  with a 90% interval; froze the rule before validating it (0/36 false alarms on unchanged
  code, prompt-cache regression blocked 6/6). Recorded product demonstration:
  furnace-5h6.pages.dev.
- Built its GitHub App integration (FastAPI, Postgres job queue with leases, Docker sandbox,
  HMAC-verified webhooks), verified on a public repository using a local GPU runner: a new
  commit's webhook queued a check that blocked a +575% TTFT regression on that exact commit
  (redeliveries deduplicated), and the drafted fix passed the repair acceptance criteria with
  latency close to baseline.

These replace the earlier variants. The website is a recorded demonstration (no live runs);
the GitHub integration was verified with the runner on the laptop, not a hosted service.

## Sources and what to say if asked

| phrase | source | say in an interview |
|---|---|---|
| 0/36 false alarms; blocked 6/6 | `bench/results/2026-10-12-gate-validation/validation/report.md` | 36 unchanged-code trials (PASS 29, INCONCLUSIVE 7); design frozen in `docs/gate-revision.md` before any trial; 3 affected trials replaced as planned (63 recorded) |
| 15/18 undecided | same report, graded sets | regressions sized at +13 to +30% measured +4 to +7% in the gate; detection near the 10% tolerance is not shown |
| 193-433% | `bench/results/2026-10-06/rq4/rq4.md` | max-num-seqs 32, every cell, same sign in every paired repeat, laptop RTX 3050 Ti at 780 MHz, Qwen2.5-0.5B |
| 46%; 13/13 | `bench/results/2026-10-06/rq3.md` | 13 scripted PRs on fixture F1, under the gate of that date (a p95 point rule later found biased); the selection does not depend on the gate, the perf verdicts do |
| 3/3; 86% below the PR; within 4.2% of main | `bench/results/2026-10-12-gate-validation/rq5.md` | three repeated trials of **one** scenario (fixture F1, regression R1), not a rate over apps; the first strategy was rejected by the same gate; repaired prompts byte-identical to main for 34/34 questions |
| +575%; exact commit; redeliveries changed nothing | `bench/results/2026-10-14-live-webhook/NOTES.md` | one fresh commit (49224d2) on PR #4 of `dilipna/furnace-demo-f1`: GitHub's signed delivery → job → laptop runner → check run 116037356084 on that head, `failure`, geometric-mean TTFT 73.6 → 496.9 ms (90% interval +509% to +649%); GitHub redelivered the same event twice (during and after the job): no new rows, one check run. First and only attempt. Receiver ran on the laptop behind a smee relay, not a hosted API |
| fix passed the repair acceptance criteria, latency close to baseline | `bench/results/2026-10-14-live-github/NOTES.md` (repair step) | the accepted fix measured -1.6% vs main, 90% interval -9.1% to +6.6%: it crosses zero, so it is **not** an improvement over main; it met the acceptance rule (no worse than main within tolerance, far below the PR's +593.5%) in this one scenario. The first strategy was rejected (+36.1%) |
| GitHub App, check runs, draft PRs; verified on a public repository | `bench/results/2026-10-14-live-github/`, `docs/security.md` | 390+ tests against a mock GitHub, then one live run on a public repository: check run on the PR head, draft fix, independent verification 10/10. The first attempt hit a 403 (workflow files need a permission the App does not hold); a good story about least privilege if asked |

## Do not write

- "customers", "users", "pilots", "startup raised", "investor": none has happened.
- "auto-repair" or "fixes regressions" without "one regression family".
- "-1.6% faster than main" or any improvement over main: its 90% interval (-9.1% to +6.6%)
  crosses zero. Say it passed the repair acceptance criteria and returned latency close to
  baseline in this scenario.
- "production-ready"; "deployed" only for the recorded site once its URL passes
  `scripts/smoke_hosted.py` (the API, scans and live runs are not hosted).
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
