# Local issue 001: repair verification without performance evidence

Status: open; recorded during the Guard retry review, not implemented in that change.

Affected paths:

- `packages/furnace/src/furnace/cli.py`: `gh-repair --no-endpoint` and `_target`.
- `packages/furnace/src/furnace/github/flows.py`: `repair_pr` supplies no perf callback when target is absent, then permits a verified repair to reach draft-PR creation.
- `packages/furnace/src/furnace/guardian/repair/loop.py`: `perf_check is None` satisfies acceptance and can yield `RepairStatus.verified`.
- `packages/furnace/tests/test_repair.py`: `test_repair_loop_writes_failing_test_first_and_verifies` exercises the unmeasured loop.

Reproduce locally, without GitHub credentials or a GPU:

1. Install the locked Python environment and start Docker.
2. Run `uv run pytest packages/furnace/tests/test_repair.py::test_repair_loop_writes_failing_test_first_and_verifies -q`.
3. Inspect its call: it supplies no `perf_check` and asserts `RepairStatus.verified` after real sandbox tests. The loop's `outcome.perf` remains empty on that path.
4. Trace `gh-repair --no-endpoint` to the same path. With `--open-pr`, the flow checks status/files, not the presence of perf evidence. Do not open a remote PR merely to reproduce this issue.

Observed: functional tests alone can earn the same verification label used for a performance-verified repair. The draft-PR branch is confirmed by code inspection; no remote PR was opened through this bypass. Event-driven repair normally supplies a target.

Expected: missing performance evidence must remain explicit throughout status, CLI output and PR text. A repair described as having passed the performance gate must actually have the required passing measurement. Offline functional validation can remain useful, but must not silently satisfy the performance-verification contract.

Acceptance criteria:

- Cover the no-endpoint path through CLI/flow and loop with no model calls.
- A missing, skipped, failed or inconclusive required measurement cannot produce a fully performance-verified claim or bypass that gate when opening a PR.
- If offline draft proposals remain supported, identify them as functionally tested and performance unverified in machine-readable output and reviewer text.
- Preserve the existing acceptance thresholds and unfavorable measurement results.
- Preserve successful fully measured repair behavior and refusal of unsupported regressions.

An implementation decision about offline draft proposals belongs to this follow-up; it is not needed for the Guard retry fix.
