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
