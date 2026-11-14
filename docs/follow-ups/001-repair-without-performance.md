# Local issue 001: repair verification without performance evidence

Status: fixed on the local repair-verification branch; local regression/mock and real
sandbox verification, with live demo validation still required. No new measured inference
or remote draft PR was executed. This is stacked on unmerged PR #5 at `d1dfad9`.

The original defect and reproduction below describe **that baseline**, not the new behavior.
See [the verification contract](../repair-verification.md) for state/compatibility rules.

Affected paths:

- `packages/furnace/src/furnace/cli.py`: `gh-repair --no-endpoint` and `_target`.
- `packages/furnace/src/furnace/github/flows.py`: `repair_pr` supplies no perf callback when target is absent, then permits a verified repair to reach draft-PR creation.
- `packages/furnace/src/furnace/guardian/repair/loop.py`: `perf_check is None` satisfies acceptance and can yield `RepairStatus.verified`.
- `packages/furnace/tests/test_repair.py`: `test_repair_loop_writes_failing_test_first_and_verifies` exercises the unmeasured loop.

Reproduce locally, without GitHub credentials or a GPU:

1. Install the locked Python environment and start Docker.
2. On baseline `d1dfad9`, run `uv run pytest packages/furnace/tests/test_repair.py::test_repair_loop_writes_failing_test_first_and_verifies -q`.
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

## Resolution and current verification

- No callback now means `functional_only`, with performance unverified; explicit offline
  drafts have an UNVERIFIED title/body and a separate versioned branch namespace.
- Required measurements must have complete finite current interval evidence and satisfy
  the existing rule. Missing/skipped/error/malformed results, exceptions and non-finite
  values reject the candidate. The GitHub write boundary rechecks the contract.
- Actual acceptance, files, callback counts and write-token/draft creation are asserted by
  `test_repair_verification.py`; GitHub, inference and sandbox boundaries are mocked there.
- The existing real-Docker repair test is now named
  `test_repair_loop_writes_failing_test_first_and_validates_functional_only`. It retains
  failed-on-head/passed-on-base reproduction and validates the unmeasured distinction.
- A read-only compatibility test retains all three saved G3 accepted repairs, without
  modifying their results or claiming new inference. Guard retry/queue tests remain in scope.

Run `uv run pytest packages/furnace/tests/test_repair_verification.py packages/furnace/tests/test_repair.py packages/furnace/tests/test_gate_stats.py packages/furnace/tests/test_guard_execute.py -q`.
Run lint, formatting, import boundaries and Pyright, plus the committed-tree Linux Python
checks as recorded in the delivered review. The [targeted live plan](../pilot/live-validation.md)
remains an unexecuted next step; no production-readiness claim is implied.
