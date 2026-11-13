# Furnace Studio local application

Studio is the application-first workspace for the owner’s researcher-infrastructure
product. It uses existing Python/FastAPI dependencies; no cloud service or paid resource
is created. $20/month is configured as the managed-service offer. Both compute ownership
choices are available. Billing, model execution and provisioning are inactive in this build.

## Run from source

Prerequisites: Git, Python 3.12 and uv. From the repository root:

```sh
uv sync --frozen
uv run furnace studio
```

Studio binds to 127.0.0.1:8787 and opens the local session URL after the server starts.
Use `--no-browser` to open the printed URL manually, `--port` for another loopback port,
and `--workspace PATH` for a dedicated local data directory. The default is
`~/.furnace/studio`. No API/database/GPU/Docker setup is needed for workspace features.
Do not publish its port, share the session link or place secrets in project fields.
The session token changes on restart; saved projects remain. A stale tab must open the
new session link. This is local-session security, not hosted multi-tenant authentication.

## User journey

1. Name a project and enter the absolute folder path on the machine running Studio.
   Inspect files: bounded metadata only, no model imports or checkpoint loading.
2. Review detected files and six unverified capability areas. Download the free kit.
3. Save architecture, task, revision, license, device and input/output/loading notes.
4. Choose Furnace-provided or customer-provided compute and explicit demo resource/
   retention preferences. Saving does not purchase, provision or validate infrastructure.
5. Add representative sanitized evaluation cases. They remain not_run. Downloaded kits
   include the saved snapshot, contract, cases and preferences.
6. Check launch readiness: without a validated adapter it reports why no server started.
7. Review real workspace activity; remove a record only after the inline confirmation.
   Removal preserves model files and existing exports. The demo has two project slots.

Activity is assessment/configuration history, not model inference telemetry. Model logs,
executed evaluations and actual serving depend on the subsequent adapter implementation.
The application does not claim a complete managed model environment is already running.

## Build the download

```sh
uv run python scripts/build_studio_bundle.py
```

Output: `dist/furnace-studio-preview.zip`, containing three local workspace wheels,
pinned dependency requirements, a Python launcher, instructions and wheel hashes.
Extract to a new directory and run `python launch.py`. Python and uv are prerequisites;
first launch resolves pinned dependencies and may obtain the Python runtime through uv.
It is a wheel-based preview, not a native signed installer. User models, local databases,
.env files and private session logs are excluded. No public upload is performed.

## Validation and limits

Direct API tests cover persistence across application recreation, actual ZIP content,
snapshot identity, cases staying not_run, no launch on missing adapter, auth/origin/host
checks, bounded request bodies, field validation, duplicate projects, two-project limit,
static assets and source-preserving deletion. Existing starter and repair CLI checks
remain applicable. Packaging and real HTTP smoke results are in the local handoff.

Browser automation could not connect during this turn. Visual layout, keyboard flows,
actual browser downloads, mobile rendering and human comprehension remain unverified;
passing API tests do not substitute for those checks. No real model, GPU, remote server,
cloud account or payment flow was exercised. See [research](model-support-research.md)
for what a model support contract must prove next.

## Manual review checklist (results intentionally blank)

| Task | Completed | Confusion / assistance | Actual observations |
| --- | --- | --- | --- |
| Explain intended customer, free kit and $20/month offer | | | |
| Inspect a local test project and distinguish detection from verification | | | |
| Save model contract and switch compute ownership | | | |
| Add a case and explain why Not run is not a pass | | | |
| Download and inspect kit; check readiness refusal | | | |
| Restart application, reopen private session and find saved project | | | |
| Use keyboard only and a narrow viewport | | | |
| Remove a record and confirm source/checkpoints remain | | | |

Stop with Ctrl+C in the application terminal. For uninstall, remove only the extracted
bundle and the dedicated workspace directory after reviewing retention. Do not delete
shared uv caches, model folders or unrelated resources.

## Application milestone verification (2026-11-13)

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
