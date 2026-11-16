# Case-suite import verification — 2026-11-16

Application source: `64798eb7d33e30cf779b7064e3b2b9231d42e1a1`.
Visual-check harness: `83b0e9a5c73c2b94a0a26e479ad27bfe490d85c1`.
The second commit only adds screenshot/overflow coverage; application code is identical.
All work remains on the local `product/local-model-endpoint` branch, unpublished.

## Capability completed

Studio's UI previously required entering cases individually, while starter kits already
exported JSONL case files. **Evaluations → Import an evaluation suite** now previews
those files locally and replaces the saved suite only after an explicit action.
The [user guide](case-suite-import.md) defines the format, limits and privacy contract.

- `case-import.mjs` validates bounded UTF-8 JSONL and field types/lengths, preserves
  exact text and Unicode code points, and strips imported status metadata. Invalid
  errors identify lines/fields without echoing malformed content.
- `studio.js` owns previews by project and guards delayed/superseded reads. Preview
  and discard do not save cases or execute models. A relevant configuration change
  invalidates the preview. Unsaved previews participate in the tab-close warning.
- The existing case API accepts an optional `expected_configuration_sha256`. Import
  sends it; `RuntimeService.update` checks it inside the project lock before writing.
  A stale request returns 409 without changing saved cases. Existing manual callers
  remain compatible. Case validation, the 64 KiB body limit and execution rules remain
  in force; `status` still cannot be supplied as a saved case input through the API.
- Saved imported cases start `not_run`; descriptions remain unscored. No result,
  quality verdict or model-support claim follows from importing a label. Existing
  endpoint attempt history is preserved and evaluated against its configuration identity.

No application dependency, paid service, billing/provisioning operation or evaluation
threshold was added or changed. `scripts/ci_linux.sh` now stages the new parser module
alongside the existing Node state-test assets; hosted CI's full checkout already
contains it. This keeps the local verifier reproducible as the test imports expand.

## Executed checks

| Check | Result and scope |
| --- | --- |
| Full Linux Python runner at `64798eb` | 596 passed in 157.68 seconds; one existing Starlette/httpx warning. Ruff check/format, both import contracts, Pyright and Postgres migrations passed |
| Parser/state suite | 18 passed on Windows Node and Linux Node 24, including kit JSONL round-trip, discarded labels, whitespace, Unicode, malformed/unknown fields, UTF-8, case-count and normalized request-size limits |
| Focused Windows API/onboarding/identity tests | 6 passed. Stale/foreign identities and labels are rejected; queued replacement checks the identity after waiting for the lock; cases and revision remain unchanged on refusal |
| API image at `83b0e9a` | Build and `furnace_api.main` import passed |
| Installed preview | Passed outside the source checkout on Linux/Python 3.12.12, uid 10001, read-only root and empty uv cache; no Docker CLI/socket available to Studio |
| Installed Chromium | Passed on 153.0.8010.12. Invalid preview left revision/cases unchanged, delayed read stayed with its project, a concurrent contract edit produced 409, fresh preview saved two `not_run` cases, other project's cases stayed empty, and exported kit JSONL previewed safely |
| Visual QA | Import-ready desktop 1440×1000 and mobile 390×844 captures inspected. Labels, preview, explicit replacement/discard buttons and existing cases were visible; mobile horizontal-overflow assertion passed |
| Existing journey | Connector requests, failure/retry, retained history, configuration fencing, keyboard controls, stale refreshes, ZIP download, restart, session-token rotation and synthetic persisted-pageshow recovery continued to pass |

The Linux Python runner used the [documented preinstalled-Node workaround](studio-runtime-verification.md#linux-check-and-exact-workaround):
only the Python runner image differs from the repository script. No test selection or
assertion was weakened. These are local Linux results, not hosted GitHub CI. Public
Next.js builds were not rerun because no public-site source changed.

The [installed receipt](verification/case-import-visual.json) records the clean source
and the successful installed journey. The 16 actual HTTP calls in that journey went
to an explicitly labeled authored test server. Preview/replacement made no inference
calls; the subsequent connector checks account for the calls. No learned model ran.
Installation/startup timing in the receipt is not model latency.

Preview ZIP SHA-256:

```text
405ad1c75b46a8022d0eb67078c60e7f454cd444e993e4abe52889e9f53f28bf
```

To repeat, build the preview and use the existing
[installed-browser command](local-model-endpoint-verification.md#repeat-the-installed-check)
with `--connector --browser --screenshots ...`. The harness now includes this import
journey. The new parser cases run in the existing command:

```sh
node --test apps/api/tests/studio-state.test.mjs
uv run pytest apps/api/tests/test_studio_case_import.py -q
```

## Remaining limitations

This is a text-case JSONL importer, not an arbitrary dataset converter or model judge.
It replaces the complete saved suite and retains the existing 30-case/64-KiB limits.
Previews are tab memory; saved inputs/expectations are local data included in exports.
Actual owner comprehension, native file-picker usability, fresh Windows/macOS install,
other browser engines and actual BFCache usage remain unverified. The restoration
handler test uses a synthetic event. Real-model/reference validation remains pending;
no model was selected, downloaded or executed for this application-first milestone.
