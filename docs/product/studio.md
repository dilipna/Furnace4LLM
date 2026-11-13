# Furnace Studio local application

Studio is the application-first workspace for researchers who need infrastructure
around their models. The free kit and local workspace work without Docker. An optional
Docker runtime exercises the infrastructure using a deterministic fixture. **It is not
a learned model, does not load user code/weights, and provides no model-quality evidence.**
The $20/month offer and both compute ownership choices are represented in configuration;
billing, cloud provisioning and actual research-model adapters remain inactive.

## Run from source

Prerequisites: Git, Python 3.12 and uv. From the repository root:

```sh
uv sync --frozen
uv run furnace studio
```

Studio binds to 127.0.0.1:8787 and opens its private local session after startup. Use
`--no-browser`, `--port` or `--workspace PATH` as needed. Default data: `~/.furnace/studio`.
No API/Postgres/GPU setup is needed. Keep the terminal open; Ctrl+C stops Studio and its
owned workers. One process may own a workspace. After a crash, reopen the same workspace
to remove interrupted workers and reconcile partial evaluations before an explicit restart.
If Docker is unreachable, cleanup is unknown, not successful; recover Docker and retry stop.
Do not expose the port, share session links or enter secrets. Tokens rotate on restart;
open the newly printed link in stale tabs. This is local-session security, not hosted
multi-tenant authentication. Local SQLite/case/kit content is not encrypted by Furnace.

## User journey

1. Name a project and enter its absolute local folder. Inspection reads bounded metadata
   without importing source or loading checkpoints. Review detections as unverified.
2. Download the free kit. Save the architecture/task/revision/license/device contract.
3. Save compute ownership and demo preferences. Saving does not buy or provision anything.
4. Add sanitized cases and optional exact expected outputs. Descriptions alone are unscored.
5. For **infrastructure testing only**, install/start local Linux Docker (Docker Desktop
   with Linux containers on Windows). Choose Prepare local test environment. It builds the
   existing reviewed Python sandbox image if absent; public packages/images may download.
6. Select “Infrastructure fixture — not a model”, approve local execution and start.
   Readiness is checked against the actual container. Send `hello` to receive
   `framework:HELLO`. This deterministic uppercase function has no learned parameters.
7. Run framework evaluations. Exact equality gives framework_pass/framework_fail;
   descriptive-only cases are unscored. Error/interruption leaves missing cases not_run.
8. Inject error/timeout/crash, confirm failed status, then explicitly restart. Stop before
   editing configuration/cases. Activity records real request IDs/durations, not raw
   request/response contents. Downloaded kits include the saved evaluation snapshot.
9. Stop or remove the workspace record. Removal first confirms owned-worker cleanup and
   preserves model files/exports. The demo has two project slots.

## Boundaries and execution evidence

The worker runs as uid 10001, no network or published ports, read-only root, dropped
capabilities, no-new-privileges, 256 MiB RAM, one CPU, 64 processes and a 16 MiB tmpfs.
Only the authored worker file is mounted read-only; project folders, weights, Docker
socket and host secrets are not passed into it. A Docker daemon remains trusted host
infrastructure; these flags are not a proof against arbitrary hostile code. Unreviewed
model adapters are refused. Only local unix/npipe Docker endpoints are accepted and
pinned for the manager lifetime. No remote compute is provisioned by either compute choice.

Requests are capped at five seconds (or a lower configured timeout); an evaluation has
30 seconds for prediction calls plus Docker control/cleanup overhead. Stop requests cancel
between cases. Each case result is persisted before the next. On recovery, a running
attempt becomes interrupted; completed case evidence remains, missing evidence is never
promoted. Configuration changes invalidate evaluation results. Each explicit run executes
again with a new run/request identity. A workspace OS lock prevents concurrent app owners.

Memory and retention form values are future managed-demo preferences; the fixture uses
the fixed limits above. Activity retains at most 100 events, not the selected day-based
retention policy. Inputs/case expectations are stored locally and included in exports;
only ad-hoc request inputs/outputs are excluded from activity logs. No remote log collector,
GPU monitor, hosted authentication, payment flow or production SLA is implemented.

## Build and install the download

```sh
uv run python scripts/build_studio_bundle.py
```

Output: `dist/furnace-studio-preview.zip`. Extract into a new folder and run:

```sh
python launch.py --no-browser --workspace /path/to/dedicated-workspace --port 8787
```

The ZIP contains three workspace wheels, pinned dependency requirements, launcher,
instructions and wheel hashes. Python 3.12 and uv are prerequisites. First launch needs
registry access unless all pinned metadata/packages are cached. It may obtain Python
through uv. This is a wheel-based preview, not a native signed installer; hashes detect
corruption, not publisher identity. User models/databases/session logs/env files are excluded.
Docker is optional until explicitly exercising the infrastructure fixture.

For uninstall, stop normally and remove only the extracted bundle and reviewed dedicated
workspace directory. Do not delete shared caches or model folders. Reopening a crashed
workspace for cleanup must happen before discarding its metadata.

## Reproduce targeted verification

With frozen development dependencies and local Docker running:

```sh
uv run pytest -q apps/api/tests/test_studio.py packages/furnace/tests/test_starter.py packages/furnace/tests/test_runtime_manager.py apps/api/tests/test_studio_runtime.py packages/furnace/tests/test_workspace_lease.py
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pyright
node --check apps/api/furnace_api/studio_assets/studio.js
```

New runtime integration tests require Docker and intentionally fail if unavailable.
They inspect real container flags, mounts, IDs, request outputs, removal and recovery;
unit tests separately simulate daemon/cleanup failure. No GPU/model inference is tested.
For full committed Linux checks, use `bash scripts/ci_linux.sh python`; this needs Docker,
public registry access and enough Docker-VM disk space. Local Windows pytest is not Linux CI.

## Human review (no participants yet)

Two participants should work independently. Record observations only after participation;
browser automation is not evidence of comprehension.

| Task | Participant 1 observation | Participant 2 observation |
| --- | --- | --- |
| Explain intended customer, free kit and $20/month offer | | |
| Distinguish local fixture execution, recorded historical demo and live model inference | | |
| Explain a framework result and why it says nothing about model quality | | |
| Determine Python/uv/Docker prerequisites for the desired feature | | |
| Inspect a project, save contract/preferences and find the next action unaided | | |
| Run an exact check, inject a failure, recover and stop | | |
| Use keyboard, download kit and recover a saved project after restart | | |

Smallest remaining clean-environment onboarding test: fresh Windows or Linux user profile
with Python 3.12 and uv, empty uv cache, no checkout or existing Furnace environment.
Extract the ZIP, install pinned dependencies, create a harmless metadata-only project,
export its kit, quit/relaunch and confirm persistence/token rotation. Then, with local
Linux Docker installed/running and no Furnace sandbox image, prepare/start/request/evaluate/
stop and verify no worker remains. Expected: instructions suffice without undocumented
steps; no research code/weights execute. Existing-machine installed-package smoke does
not establish this clean-machine result.

Current runtime milestone evidence: [verification record](studio-runtime-verification.md).

## Historical workspace milestone (2026-11-13, before runtime implementation)

Application source commit: 842e0ec93b825e181304b55887bb58043ce51817.
- Whole-repository Ruff, formatting and Pyright passed through the frozen uv workspace;
  import boundaries passed (2 kept). JavaScript syntax check passed.
- Final Studio + starter tests: 19 passed, 1 Windows symlink-permission skip, 1 existing
  Starlette/httpx deprecation warning. Assertions inspect actual SQLite persistence,
  ZIP bytes, saved settings/cases, auth/refusal behavior and untouched source files.
- Broader relevant CLI/repair/setup run: 75 passed, 1 skipped, 1 warning and 1 setup error.
  The failing existing poller test required unavailable Postgres. Its exact case was
  then rerun against a fresh disposable Postgres with real migrations: 1 passed; the
  container was stopped/removed. No test, threshold or requirement was weakened.
- Focused Linux application check passed using an existing API image, non-root user,
  no network and read-only source mount. Real symlinks were excluded; actual project,
  preferences, ZIP, persistence, deletion and missing-runtime refusal were checked.
  This is not the full Linux CI job or a fresh image build of this branch.
- Built three wheels and a downloadable ZIP. The wheel contains UI assets and the
  furnace-studio entry point, and excludes local databases/session logs/env files.
  Extracted package ran in an isolated uv tool environment outside the checkout.
  First offline launch lacked dependency registry metadata; permitted first-launch
  dependency resolution installed 57 pinned packages. No model weights were fetched.
- Real loopback HTTP flow passed on installed wheels: assets, session/origin guards,
  project creation, both compute modes across API/HTTP tests, cases staying not_run,
  kit download, refused unconnected start and source-preserving removal.
- Final bundle restart with the same workspace preserved a saved project, rotated its
  token, rejected the old token and rejected an oversized request. Tampering with a
  bundled wheel caused the launcher to refuse it before installation. Hashes detect
  corruption, not publisher authenticity; this is not a signed installer.
- A direct Pyright invocation selected the wrong Python environment and reported
  unresolved workspace imports; `uv run --frozen --offline pyright` passed with 0 errors.

Browser automation could not connect (two timeouts). No visual/mobile/keyboard or actual
browser-download success is claimed. No real model, new GPU measurement, executed model
quality evaluation, remote provisioning, payment, customer onboarding or human feedback.
The model runtime is deliberately unconnected; infrastructure preferences are not a
provisioned service, and workspace activity is not inference telemetry.
