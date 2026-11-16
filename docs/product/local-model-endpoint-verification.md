# Local connector verification — 2026-11-15

Follow-up on 2026-11-16: [bounded attempt history](evaluation-history-verification.md)
adds failure retention, a newer verified preview and fresh checks. The source IDs and
archive hashes below describe the earlier milestones and remain historical evidence.
The subsequent [case-suite import milestone](case-suite-import-verification.md) adds
safe JSONL preview/replacement and records the latest installed preview and checks.

Initial connector source: `761bd37ac393a36e1da14359202048d55da9900a` on
`product/local-model-endpoint`, based on the existing Studio branch at
`bdbedca5add63bd1778e8bdeec540f3cc14dbbbd`. This is local, unpublished development.
The existing review branch and visitor-journeys branch were not changed.

## Evidence boundaries

The new tests run actual HTTP requests against stdlib loopback test servers. Those
servers return authored text and never run a learned model. Their successful
responses establish transport/application behavior only. The existing Docker tests
exercise the deterministic infrastructure fixture. Neither is new inference evidence.

The connector suite verifies actual outbound request counts/bodies and saved state:
settings and refused consent issue no requests; readiness issues only GET; inference
issues POST; errors stop the batch; blocked retries issue nothing; explicit reconnect
and retry execute both cases again. Disconnect during an in-flight HTTP call records
an interrupted attempt, suppresses the remaining case and requires reconnect. Restart
retains partial evidence without reconnecting. A copied result cannot verify another
project. A changed declared revision clears endpoint evidence. ZIP content is checked.

Review also separated endpoint errors from the pre-existing fixture error formatter
and kept timeout cancellation from clearing HTTPConnection state in another thread.
Slow-response and slowly trickling-body tests exercise the real deadline behavior.

## Local checks

- Windows: all 50 affected Studio tests passed after starting Docker Desktop. An
  earlier run had 45 passes and five `docker_unavailable` failures while the engine
  was stopped. The final connector suite passed all 27 tests after the timeout-thread
  correction. One existing Starlette/httpx deprecation warning remains.
- Shared JavaScript state tests: 12 passed. The new module passes Node's ES-module
  syntax check. These checks do not execute the new page in a browser.
- Windows source lint, formatting, import boundaries and type checks passed. Direct
  invocation of Pyright initially selected the wrong interpreter; selecting
  `.venv/Scripts/python.exe` resolved imports. New test-fixture event attributes were
  then declared explicitly and type analysis reported zero errors.
- Saved historical evidence: 12 runs / 720 measured requests verified against the
  existing published tables with `python experiments/prefix-cache/review.py`. This
  verifies saved measurements; no historical experiment was rerun.

Final committed-tree Linux results at `761bd37`:

| Check | Result |
| --- | --- |
| Ruff check and format | Passed |
| Import boundaries | Both contracts kept |
| Pyright | Zero errors or warnings |
| Postgres migrations | Passed |
| Full non-GPU Python suite | 592 passed in 285.82 seconds; one existing deprecation warning |
| API image build and import | Passed |

The earlier `0d65a53` Linux run was stopped after the timeout-thread correction
superseded it. It supplies no completed-suite pass claim. The final head ran the full
selection to completion. No failing assertion or unfavorable result was removed.

The local Linux runner uses `scripts/ci_linux.sh` with exactly one substitution:
`ghcr.io/astral-sh/uv:python3.12-bookworm` → the existing
`furnace-review-toolchain:repair-verification` image in `run_python`. A diff of the
runner copy against the repository script confirmed that single change. The
[previously documented toolchain recipe](studio-runtime-verification.md#linux-check-and-exact-workaround)
adds preinstalled Node for Pyright. The stock nodeenv failure is historical; the
unmodified Python bootstrap was not rerun for this milestone. Repository CI and its
thresholds remain unchanged.

The runner archives committed HEAD and tests as uid 1001 with real Postgres,
migrations and Docker sandbox execution. Its Python steps remain `uv sync --frozen`,
Ruff check/format, import-linter, Pyright, Alembic and `pytest -q -m "not gpu"`.
The image job builds the committed tree and imports `furnace_api.main` in that image.
These are local Linux checks, not hosted GitHub CI. The unrelated public Next.js
builds were not rerun; no public-site source changed in this branch.

## Local preview artifact

`uv run --frozen python scripts/build_studio_bundle.py` completed at clean source
`761bd37ac393a36e1da14359202048d55da9900a`. The ZIP's manifest and all wheel hashes
were checked, and the connector's HTML, JavaScript and Python modules are included.
SHA-256 of `dist/furnace-studio-preview.zip`:

```text
ae4495b9effb22a1f32ba6bf42a3811ac716130c730d05fad09ac4c51210d92e
```

This initial artifact subsequently passed a fresh empty-cache Linux installation
check for startup, workspace metadata, exports, restart, persistence and token rotation.
That first check did not exercise the connector page. The updated artifact and full
connector checks are recorded below. Earlier installed-bundle evidence for `bdbedca`
does not establish behavior of the new connector. All artifacts remain unpublished.

## Installed connector and browser gates completed

Final executable source: `de1b461a72e19e56e6973284e8b9bfa64b79e596`.
The subsequent handoff commit only adds documentation and the verification image recipe.
The only application change since `761bd37` is nine added/changed lines in `model.js`.
The Python endpoint implementation, dependencies and acceptance rules are unchanged.

The installed-browser checks found and reproduced two defects:

1. Hold the response to Refresh saved state, delete a second project, refresh again,
   then deliver the older response. The installed `761bd37` archive displayed one
   project after the fresh response, then incorrectly displayed two after the stale
   response. A refresh generation now fences both successful and failed old responses.
   The same installed check at the final source records one project after both responses.
2. Fail a refresh in the persisted-pageshow handler, then retry successfully. The
   installed `e6582af` archive restored completed evidence but kept the contradictory
   “Saved state not confirmed: Failed to fetch” notice. A new refresh now clears that
   stale notice. The final installed check requires the notice to disappear on recovery.

Neither failed assertion was removed. The final run also verifies a delayed failed
refresh cannot overwrite a newer success. The regression waits for intercepted
requests to finish and browser promise handlers to render before inspecting absence.

The [machine-readable receipt](verification/connector-de1b461.json) records the clean
source, bundle hash and outcome. It contains no session token or prompt logs.
Final ZIP SHA-256:

```text
de7c48280c2117053f4d2c4a4874eda4bb9926b7d6b85918f485a202b6872ad9
```

| Gate | New execution evidence |
| --- | --- |
| Installation outside checkout | Passed on Linux/Python 3.12.12, uid 10001, empty uv cache, read-only root, capabilities dropped; no Docker CLI/socket or checkout available to Studio |
| Actual installed endpoint API | Passed: saving/refused consent make no HTTP request; readiness only GET; POST input checked; error interrupts; blocked retry makes no call; reconnect executes cases again |
| Evidence and restart | Passed: exact_pass and unscored remain distinct, fixture evidence stays separate, exported project/configuration identity matches, saved run survives restart disconnected, old token rejected |
| Installed Chromium journey | Passed on Chromium 153.0.8010.12; drafts and late outputs stay with their project; changed configuration fences results; ZIP download inspected; stale refresh regressions pass |
| Keyboard and restoration | Skip link moves focus to main; Tab reaches selector, refresh, all five connection inputs, save and consent in order; Space toggles consent; reload/Back issue no inference calls; synthetic persisted-pageshow failure withholds evidence and permits recovery |
| Visual inspection | Desktop 1440×1000 and mobile 390×844 full-page captures inspected; forms and buttons visible; no horizontal overflow at the mobile size |
| Affected existing checks | 31 Windows Studio Python tests and 12 shared state tests passed; JavaScript module syntax passed; Ruff check/format passed; default Pyright and explicit checks of both verification scripts report zero errors |

The installed run issued 15 real HTTP requests to an authored test server, which ran
no model. The installation/startup duration in the receipt is not inference latency.
The earlier 592-test Linux result above remains historical at `761bd37`; it was not
rerun or relabeled as a final-head suite result. No Python application code changed.
No new hosted CI or public-site build was run for this local follow-up.

## Repeat the installed check

Prerequisites on the review machine: Docker with Linux containers; Python 3.12 and uv
to build the preview. The disposable test image uses the existing Playwright 1.63.0
development dependency and downloads its browser/OS packages. This adds no application
dependency or service. Build the archive from the desired clean source first:

```powershell
uv run --frozen python scripts/build_studio_bundle.py
docker build -f scripts/studio-browser.Dockerfile -t furnace-connector-browser:local .
$bundlePath = (Resolve-Path dist/furnace-studio-preview.zip).Path
$scriptsPath = (Resolve-Path scripts).Path
New-Item -ItemType Directory -Force dist/connector-review | Out-Null
$reportPath = (Resolve-Path dist/connector-review).Path
docker run --rm --read-only --user 10001:10001 --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,exec,mode=1777,size=1g --tmpfs /uv-cache:rw,exec,mode=1777,size=1g --env UV_CACHE_DIR=/uv-cache --env UV_TOOL_DIR=/tmp/uv-tools --env UV_TOOL_BIN_DIR=/tmp/uv-bin --env PYTHONUNBUFFERED=1 --mount "type=bind,source=$bundlePath,target=/bundle.zip,readonly" --mount "type=bind,source=$scriptsPath,target=/checks,readonly" --mount "type=bind,source=$reportPath,target=/reports" --entrypoint python furnace-connector-browser:local /checks/verify_studio_onboarding.py /bundle.zip --expect-empty-cache --connector --browser --screenshots /reports/screenshots --output /reports/connector.json
```

This command shape was executed successfully for the recorded artifact. The image
recipe committed here matches the one used for that run. Docker is a prerequisite of
this review harness; installed Studio's connector itself does not require Docker.

## Unverified gates

The earlier desktop computer-use attempt ended because its helper could not reliably
determine Chrome's URL. Subsequent verification used a separate disposable Linux
Chromium process against the installed preview, with no interaction with desktop Chrome.
Fresh Windows/macOS installation, other engines and actual BFCache use remain open.
The synthetic persisted-pageshow test proves handler behavior, not a real cache hit.

No model was selected, downloaded or executed; no native loader, server provisioning,
payment, GPU experiment or hosted CI run was added. A trusted local HTTP server can
misrepresent model identity or change weights without updating its declared revision.
The connector does not resolve that attestation or external-server isolation problem.

Use the [owner-assisted checklist](local-model-endpoint.md#verification-and-remaining-gates)
for the next review. Its observation fields remain blank. The owner can review the
application without choosing a model; a model/reference case is required later to
claim real-model support.
