# Windows lease-test diagnosis and repeated full suites

Source under test: `9015d135979f4d3f12e8ce3c83dbe92fc094a42b`.
This is local Windows evidence, not Linux CI. Full raw outcomes and hashes are in
[windows-repeatability/record.json](windows-repeatability/record.json). No timeouts,
scoring rules, historical acceptance bounds or unfavorable results were removed.

## Confirmed cause of the original lease test failure

The original test slept 0.5 seconds before an unconditional SQL update. It did not
establish that a worker had claimed the job. A controlled 1.25-second delay before
claim reproduced the timeout: immediately before claim the row was still **queued**,
owned by `thief`, with attempt 1. The worker subsequently claimed it normally. The
heartbeat therefore had no lost running lease to detect. This is a test-order race,
not evidence that the worker failed to cancel a stolen running claim.

The regression now waits on an event set inside the handler, updates only a running
row owned by `w-slow`, asserts that the theft affected that row, and checks cancellation,
retained running state, new owner and attempt 2. The original 15-second wait is unchanged.
It covers normal and deliberately delayed claims; the same delayed-claim reproduction
passed both cases. Failed assertions also cancel the owned task rather than leaking it.
Worker/queue implementation is unchanged.

## Requested full-suite scenarios

| Scenario | Actual outcome |
| --- | --- |
| No Furnace model load; other project containers left alone | 731 passed, 4 skipped |
| Continuous Qwen CPU requests (70 completed, no request errors) | 731 passed, 4 skipped |
| Two simultaneous full suites, independent databases on the same PostgreSQL server — primary | 716 passed, 4 skipped, 15 failed, 5 errors |
| Parallel companion | 717 passed, 4 skipped, 14 failed, 4 errors |

The lease-cancellation test passed in all three primary scenarios, including both
parameterized claim delays. The parallel stress run is **not green**. Its logs confirm:

- PostgreSQL refused connections with `TooManyConnectionsError: sorry, too many clients
  already`. Read-only `SHOW max_connections` confirmed the task server's ceiling was 100.
  Independent database names do not provide independent server connection budgets.
- All three mock client-timing checks exceeded their existing 2 ms p50 overhead bound;
  the primary measured approximately 3.90, 6.94 and 8.99 ms. These are client/mock timing
  measurements under contention, not new model latency or a demonstrated regression.
- Studio runtime tests also returned worker-startup failures and missing expected case
  states. Their deeper cause was not captured conclusively. Do not attribute every
  stress failure solely to PostgreSQL or CPU contention.

There was concurrent developer work (including a native build and dependency setup),
so these durations do not establish a controlled speed comparison or general scaling
limit. No benchmark bound was raised. The parallel profile remains an unverified
capacity/reliability limit; it is not a supported multi-user deployment claim.

## Interrupted attempts are separate

An initial loaded run ended without a completion record when the environment/Docker
session was interrupted. A resumed attempt discovered the task PostgreSQL container was
stopped and was aborted. Both partial logs remain. Only the completed runs above count
toward the three full-suite observations. The corrected harness checked an authenticated
PostgreSQL connection before starting each completed remaining scenario.

## Owner checks

The blank [clean-account checklist](../../operations/clean-account-install.md) covers
checksum, unsigned warnings, per-user install, example/export, Quit, retention and
explicit deletion. Creating the account/Docker prerequisites is outside its ten-minute
exercise. A localhost download may not carry the same browser trust marker as a future
public download; absence of SmartScreen is not publisher verification.

The November 24 walkthrough sheet and #15/#16 were not edited. Use the installed #18 app
from Start, not Git/Python/uv or a copied session link. Existing inspection, fixture,
model, export and recovery tasks remain. Source-only setup and statements in older
rubrics that no model has been validated or that managed loading is unavailable do not
apply to current #18. The separate document branch is not in that walkthrough build.
