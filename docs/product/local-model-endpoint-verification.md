# Local connector verification — 2026-11-15

Source under review: `761bd37ac393a36e1da14359202048d55da9900a` on
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

This new artifact has not undergone a fresh installed-bundle execution test. Earlier
installed-bundle evidence for `bdbedca` does not establish installed behavior of the
new connector. The artifact remains local and has not been published or deployed.

## Unverified gates

Desktop computer use ended because its safety helper could not determine the current
Chrome URL reliably. No fallback browser automation was used. Visual layout, keyboard
operation, project switching during a late response, reload and browser Back on the
new page require actual browser verification. Shared utility tests cover identity
fencing but are not substitutes for exercising the page.

No model was selected, downloaded or executed; no native loader, server provisioning,
payment, GPU experiment or hosted CI run was added. A trusted local HTTP server can
misrepresent model identity or change weights without updating its declared revision.
The connector does not resolve that attestation or external-server isolation problem.

Use the [owner-assisted checklist](local-model-endpoint.md#verification-and-remaining-gates)
for the next review. Its observation fields remain blank. The owner can review the
application without choosing a model; a model/reference case is required later to
claim real-model support.
