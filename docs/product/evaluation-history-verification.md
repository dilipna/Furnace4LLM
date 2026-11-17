# Evaluation history — local verification, 2026-11-16

This milestone adds durable, bounded endpoint-attempt history to the existing local
Studio preview. Nothing was pushed or deployed. No research model was selected or run.

## Confirmed problem and reproduction

Before this change, `ModelService.evaluate` replaced `model_evaluation` on every
attempt, and connection reconfiguration cleared it. The earlier failure was lost after
a successful retry. The existing HTTP regression was extended to retain the failed
run ID and require it in the project after reconnect/retry. It failed before the fix:
`AssertionError: Retry erased the failed attempt`. The HTTP test server issued a real
500 response followed by successful authored completions; it never performed inference.

That assertion remains in
`apps/api/tests/test_studio_model.py::test_actual_requests_state_identity_export_and_failure_then_explicit_retry`
and now passes. The test also requires the interrupted and completed attempts in order,
matching ZIP-export history, a new request for each retry case and stale configuration
labels after an edit. This tests actual execution, persisted metadata and exported data.

## Implementation and contract

- `studio_model.py` saves the current run and its history in one SQLite project update
  after start, each case and completion/recovery. Updates replace the same run ID;
  they do not create extra attempts. Existing project locks serialize edits/evaluation.
- `studio_model_evidence.py` retains the last ten attempts in start order. Failures,
  interruptions and successes share the same retention policy. A legacy last run is
  included without inventing old case counts or reconstructing overwritten attempts.
  Foreign-project records cannot become this project's history. Configuration matching
  is recomputed, and history never establishes readiness or the current verdict.
- Studio's **Attempt history** uses native disclosure controls and plain text. It
  labels current versus earlier/unbound configurations and exposes per-case metadata.
  Unchanged history keeps its disclosure/focus state through unrelated UI updates.
- Starter-kit `model_endpoint.history` exports the retained records and states the
  limit. Raw prompts, raw outputs and prior case text are not added to history.
  Export before editing cases/contract or expiring old attempts if their original
  inputs must remain reproducible. Project removal removes its local history.

No evaluation rule, protocol identity or performance threshold changed. `completed`
still describes request completion, not passing answers or model quality. A history
entry matching the saved configuration is not independent attestation of model weights.

## New verification evidence

Backend source: `19dc225a0ef7421794adce9f5fabd24d7f496f02`.
Installed preview/UI source: `6b932052b8f7e7a3adf75153e194e77de3cda56f`.
The latter changes only the history-disclosure rendering and its browser regression
relative to the backend source; Python application code is identical.

- Windows endpoint suite: **29 passed**, including actual HTTP failures/retry,
  cancellation, restart, partial recovery, ten-attempt FIFO retention, legacy records,
  configuration restoration without reconnect and ZIP history. One existing
  Starlette/httpx deprecation warning remains.
- Shared JavaScript state suite: **12 passed**; the served JavaScript module's syntax
  check passed. Ruff check/format and Pyright passed, including explicit type analysis
  of the installed-verification scripts.
- Installed preview: passed outside the checkout on Linux/Python 3.12.12, uid 10001,
  with an empty uv cache and read-only root. No Docker CLI/socket or source checkout
  was available inside Studio. The run used Chromium 153.0.8010.12 and the existing
  [repeatable browser verification recipe](local-model-endpoint-verification.md#repeat-the-installed-check).
- The browser inspected the failed attempt with the keyboard without making a model
  request, preserved its expanded state during a separate request, exported its metadata,
  kept three prior attempts labeled as earlier configuration after an edit, withheld
  history on failed refresh, and retained four IDs across restart. The complete run
  made 16 real HTTP requests to the explicitly labeled test server, with no inference.
- The first installed-browser run exposed disclosure/focus loss from rebuilding the
  list on unrelated updates. That failed check was retained; rendering now keeps an
  unchanged history DOM and the final installed run passes.

The [machine-readable installed receipt](verification/history-6b93205.json) binds the
successful run to its clean source and ZIP hash. Archive SHA-256:

```text
1b1e11fcdacb9b66535373af27a28b8457c7b1340d7783ba40df923e9ee5c806
```

Full Linux Python verification at `19dc225a0ef7421794adce9f5fabd24d7f496f02` passed:
**594 tests in 220.02 seconds**, with the existing deprecation warning. Ruff, formatting,
both import contracts, Pyright and Postgres migrations also passed. This used the
previously documented local preinstalled-Node runner workaround; no selection or
threshold changed. The API image build/import passed at the installed/UI source
`6b932052b8f7e7a3adf75153e194e77de3cda56f`. These are local checks, not hosted CI.
Earlier results remain attributed to their original commits in the connector record.

## Remaining limits

The ten-attempt bound is an explicit local retention limit, not managed-service
retention. Already overwritten attempts from older previews cannot be recovered.
History contains metadata and hashes, so it cannot reconstruct an old prompt/output.
The model identity and revision remain declared by the operator, not independently
verified. Real-model/reference validation, actual owner usability feedback, fresh
Windows/macOS installation and actual BFCache use remain unverified. No human-test
observations were invented; automated browser checks do not establish comprehension.
