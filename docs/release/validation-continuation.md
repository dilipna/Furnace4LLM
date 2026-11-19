# Validation continuation — 2026-11-19

The integration remains a draft; no merge, deployment, billing or new GPU experiment.
The owner's test checkout and original ZIP remain unchanged.

## Corrected evidence defect

While reviewing `scripts/validate_managed_model.py` before another real-model trial,
the finalizer was found to write `result: passed` whenever the failed-check list was
empty, even if an exception or Ctrl+C aborted the procedure before it ran its checks.
The process still exited unsuccessfully, but the retained JSON falsely claimed success.

Reproduction: replace Studio startup with a raised `RuntimeError`, `SystemExit` or
`KeyboardInterrupt`, invoke the validator and read its saved JSON. All three regression
cases failed before the fix because the recorded result was `passed`.

The validator now starts with `completed: false`, records the exception type as a failure,
preserves the original exception/exit, and requires completed execution plus no failed
checks to record a pass. Exception messages are not copied into evidence because they can
contain private server data. The saved-report checker also rejects an explicit incomplete
record claiming success; historical records without the new field remain supported.

Verification: nine focused recorder/report tests pass; Ruff and formatting pass; saved
historical model evidence still passes `render_model_validation.py --check`. No historical
JSON, score, acceptance rule or threshold was changed.

## Execution evidence

Additional runs are recorded below with their exact source after completion. Empty-cache
installation is not a fresh Windows user-profile test; an automated CPU inference trial
is not human comprehension, GPU evidence or a performance comparison.
