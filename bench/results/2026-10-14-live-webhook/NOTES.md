# Fresh-commit webhook run, 2026-10-14 (18:45 UTC): PASS, first attempt

Closes the gap left by the live GitHub run of the same day (`2026-10-14-live-github/`), where
the webhook-queued job found its head already checked and reused that check run. Here the
head commit was new, so nothing could be reused. Recorded by `scripts/live_webhook_run.py`
(code eeb419a) in `webhook_run.{json,md}`; this was the only attempt.

Setup: API on :8010 with the App's webhook secret, the App's deliveries forwarded byte for
byte by smee-client (channel URL not recorded), the Guard runner and the lab vLLM on the
laptop (AC power; GPU clock not pinned: a demonstration, not a measurement campaign).
Repair consent off (`FURNACE_GUARD_AUTO_REPAIR` unset).

| step | what was observed (read from GitHub or the database) |
|---|---|
| commit | branch `webhook-recheck-20261014-1845` from `r1-request-id` (0a637d7) plus one README line, head **49224d282d101806e2f43873a7f22ca15a839e8a**, pushed with the owner's git credentials |
| pr | https://github.com/dilipna/furnace-demo-f1/pull/4 (non-draft, into `main`), opened with the App's PR token as the live run opened PR #2 |
| delivery | GitHub delivery `61c93440-c7ff-11f1-8f9e-466f538a0d5c` (`pull_request`/`opened`, 18:45:11Z), answered 200; row in `webhook_deliveries`: source `push` (HMAC-verified), outcome `queued`, job `d09d0db6-8ae5-491a-af9e-1d97a56deafb` |
| redelivery while running | GitHub redelivered the same GUID while the job was `running`: answered 200; delivery rows for the GUID 1 → 1, jobs for this head 1 → 1, all `guard.pr` jobs 2 → 2 |
| job | claimed by the laptop runner, `running` → `succeeded`, 1 attempt, 102.9 s from enqueue to finish |
| check | exactly one Furnace check run on 49224d2: https://github.com/dilipna/furnace-demo-f1/runs/116037356084, by `furnace-dev-dilipna`, `head_sha` equal to the new commit, started 18:45:15Z, completed 18:46:53Z, conclusion **failure** ("2 regressions found: prompt_prefix_stable, chat_perf_gate"), 4 annotations |
| redelivery after completion | same GUID again: answered 200, rows unchanged (1, 1, 2), still one check run on the head |

Guard's verdict, from the check run (7 of 8 suite items selected; categories code, docs,
imports, prompt): perf gate geometric-mean TTFT 73.6 → 496.9 ms (+575.4%, 90% interval
+509.1% to +649.0%), BLOCK; prefix-cache hit 98% → 0%; p95 advisory +820.2%;
`prompt_prefix_stable` FAIL; citation, context budget, approval gate and unit tests PASS;
judge SKIP (no key, not a pass). The branch carries the R1 regression, so "failure" was the
expected verdict; it agrees with the check on PR #2's head (+590.0%, `2026-10-14-live-github/`).
No repair job was enqueued (consent off; `signatures: [prefix_instability]`).

What this shows: GitHub's signed delivery for a new head → HMAC check → exactly one queued
job → runner → a fresh check run attached to that exact head, and GitHub redeliveries of the
same GUID (during and after the job) change nothing. What it does not show: the dedupe of
two *different* events for one head (e.g. `opened` then `ready_for_review`), which is covered
by tests only; behaviour behind a hosted API (the receiver ran on the laptop behind smee).
