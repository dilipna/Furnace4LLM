# Live GitHub runs, 2026-10-14

Repository `dilipna/furnace-demo-f1` (public), App `furnace-dev-dilipna` (id in `.env`,
installation 171233745, selected repositories: this one only). Every attempt is kept.

## Attempt 1 (05:08 UTC, code eb5f8a4): INCOMPLETE, stopped at Forge

`attempt-1/live_run.{json,md}`. App check and branch heads passed. Forge validated its change
set in the sandbox (13 files), then opening the draft PR failed: `POST /git/trees` 403
"Resource not accessible by integration". Nothing was written to the repository.

Cause, confirmed with a probe using the same PR-scoped token (tree objects only, unreferenced,
no branch or ref changed): a normal file → 201; a file under `.github/workflows/` → 403.
GitHub needs the separate `workflows` permission for those paths. The mock GitHub used in the
tests did not model it, so this was first seen live.

Fix (40d41a3): Furnace still does not request `workflows`; Forge commits the other files and
puts the workflow file in the PR description for the reviewer to add.

## Attempt 2

Recorded in `live_run.{json,md}` beside this file, after the fix, same repository and App.
(05:11 UTC, code 3456656, clean): **PASS**, every step.

| step | result |
|---|---|
| Forge | draft PR https://github.com/dilipna/furnace-demo-f1/pull/1 (`furnace/forge-bb4d918` → main), 13 files validated in the sandbox; the workflow file is in the PR description, not committed |
| R1 PR | https://github.com/dilipna/furnace-demo-f1/pull/2 (`r1-request-id` → main, head 0a637d7) |
| Guard | check run 115692708323 on 0a637d7: **failure**, "2 regressions found: prompt_prefix_stable, chat_perf_gate"; PR +606.2% geometric-mean TTFT (90% interval +592.3 to +620.4), BLOCK; 97 s |
| Repair | first strategy (`move_dynamic_to_suffix`) rejected: +46.7% (+44.4 to +49.1), BLOCK. Second (`move_dynamic_to_log`) accepted: -0.7% vs main (90% interval -4.5 to +3.4), PR 71.3 → 500.5 ms; draft PR https://github.com/dilipna/furnace-demo-f1/pull/3 (`furnace/repair-pr2-0a637d7` → `r1-request-id`) |
| Replays | Forge and repair run again on the same commits returned PRs #1 and #3 (`reused=True`) |

One live trial on a laptop GPU, not a rate; the repair figures are this trial's own
interleaved runs. The GPU clock was not pinned for this run (a demonstration, not a
measurement campaign).

## Independent verification (05:20 UTC): **PASS**, 10/10

`verify.{json,md}`, read from GitHub and the local receiver, not from the run record:
permissions equal the manifest and the installation covers only this repository; Scan and
Guard tokens get 403 on writes; the check run is on the PR's head commit, by this App, with a
start, a completion and annotations on `app/prompts.py` (each changed hunk is annotated once
per failing check, so the two lines appear twice); both PRs are drafts by
`furnace-dev-dilipna[bot]` from `furnace/*` branches; `main` and `r1-request-id` unchanged;
one open Furnace PR per base; 3 real `pull_request` deliveries reached the receiver over HMAC
through the smee relay (outcomes: ignored, queued); a GitHub redelivery changed no rows;
unsigned, wrong-secret and tampered requests got 401.

The Guard runner was stopped during the run so the webhook-triggered job would not compete
for the GPU with the run's own Guard; that job was queued (outcome "queued") and is reported
separately below if it is run.
