# Integrated release candidate review — 2026-11-18

PR #10 was rechecked at `e582deaa04c02011c979cf114677f221f2a81def` and merged
normally as `9059479832c4e3264f2d3edd8a92e0af7ce16e2d`. The combined candidate
preserves PR #13's `b3b5f4f` ancestry and merges that main without changing tracked
content (`c359e6e`). PRs #11 and #12 remain unmerged. This is review work, not a release
or deployment. The owner's test checkout remains at `7fdcb2e` with its original ZIP.

## Confirmed defects and corrections

| Reproduction against the combined parent | Correction and regression evidence |
| --- | --- |
| Reopen a workspace with a recorded active managed launch while Docker is unreachable. Previously it became `interrupted`; a later reopen skipped required recovery. Container/network inspect failures were also treated as absence. Three regression assertions failed. | Persist `unknown` until cleanup can be confirmed; block configuration/start while unknown and retry recovery on reopen. Distinguish missing resources from failed inspection. Tests preserve a live scripted server across reopens and verify it is actually stopped after Docker returns. |
| Block preparation in a real worker, then close Studio. Previously the owner exited after ten seconds while that worker could still write; the competing-lease regression failed. Deleting a preparing project separately failed with a worker exception. | Cancel and reap the owned pull CLI, retain the workspace lease until workers exit, and cancel/drain preparation before deleting its record. Tests assert actual thread termination, queue removal, persisted state and lease reacquisition. Existing bounded network reads may delay shutdown. Killing the CLI does not promise cancellation of Docker daemon cache activity. |
| Change a saved model record to contain a false operational check, an inconsistent suite count or NaN while retaining `passed`. The renderer accepted all three (three failures, one retained-failure control passed). | Reject contradictory/nonfinite records, check per-case counters and make `--check` refuse stale documentation without overwriting it. Failed records and unfavorable quality scores remain included. Saved-evidence CI now runs this check; acceptance thresholds and historical JSON records are unchanged. |

The model page keeps resource limits in a native expandable section; selection remains
separate from download consent and execution. Guides, the ZIP README and current roadmap
now describe both managed local recipes and the existing-server connector. Security wording
acknowledges Docker-admin access to environment credentials and incomplete host-service
isolation on an internal network. These changes do not certify an arbitrary model adapter.

## Source-bound verification

Application/test source: `5dd3c1f2abbeef3180298d19aebdbb78309021a4`, clean tree.

- Windows focused regressions: **23 passed**, one existing Starlette deprecation warning.
- Ruff, formatting, import contracts and Pyright passed. Pyright was run with `uv run`
  so it uses the project environment; invoking its executable without that environment
  initially reported unresolved workspace imports.
- Desktop/mobile Edge browser journey passed; persisted managed selection retained advanced
  values without consent, Docker calls, downloads or execution. Connector checks issued
  18 actual HTTP requests to an authored server, not a model. Hardware availability was
  mocked unavailable. Screenshots were inspected for layout; this is not human comprehension.
- Separate installed Windows ZIP passed export, persistence/token rotation, shutdown/lease
  release, and eight requests to an authored HTTP server. Existing user/cache, not a clean
  Windows profile. ZIP SHA-256:
  `dc184d2f85b40e3537fd1bebf077d416742ba5550ba20da15b9ab921311396ce`.
- The same ZIP passed an empty-cache non-root Linux installation, isolated Chromium checks,
  18 authored HTTP requests, export and restart. No Docker socket was exposed to Studio.
- The first full Linux Python run at `5dd3c1f` retained **3 failed, 684 passed**. Two
  failures exposed Docker's `network NAME not found` response, distinct from the CLI's
  `No such container` form; the third asserted obsolete guide wording. `c7d5d11` fixes
  both with explicit regression coverage (10 direct tests passed). Tests were not weakened
  or retried unchanged to obtain a pass.

## Corrected candidate execution

At clean source `d70292c228e6fde53cce576a7b6e7f63b2119fb1`, the public/Studio browser
journey and both Windows and empty-cache non-root Linux ZIP checks passed again after
the Docker error correction. Current machine-readable receipts are in
`integration-verification/`; they name that exact source. The rebuilt ZIP SHA-256 is
`d82a6ee67abf560313f0c4da3bb9ee6f598b4653e88e39803815ab927953370a`.
It was not substituted for the owner's original test ZIP.

Hosted checks on that head passed: Python **688 passed, 1 skipped**, Web (including
Studio state tests and recorded-only static build), API image and saved evidence.
[CI run](https://github.com/dilipna/Furnace4LLM/actions/runs/44460512498),
[evidence run](https://github.com/dilipna/Furnace4LLM/actions/runs/44460512635).
The final documentation/receipt-only commit requires its own hosted checks; consult
the PR's exact-head result rather than relabeling these runs.

Local Linux is separate: Web/static and API-image jobs passed at `5dd3c1f`. The full
corrected rerun at `d70292c` passed lint, formatting, import contracts, types and database
migrations, then stopped after test progress reached 52%, without a final test result.
Afterward the Docker named pipe was absent and no Docker Desktop processes were present;
the cause of their disappearance was not established. This run is **incomplete**, not a
Linux pass. Hosted Ubuntu checks above completed independently. The local Python runner
used the previously documented preinstalled-Node toolchain workaround; comparison showed
only the runner image differed from `scripts/ci_linux.sh`, with checks unchanged.

## Reproduce without changing the owner's test

Use a separate checkout and workspace. Prerequisites: Python 3.12 and uv; Node 24 and
pnpm 10.28.2 for the website. Run from the checkout:

```sh
uv sync --frozen
uv run furnace studio --workspace /path/to/new/review-workspace --port 8790
```

In another terminal, from `apps/web`:

```sh
pnpm install --frozen-lockfile
pnpm exec next dev --hostname 127.0.0.1 --port 3010
```

Open `http://127.0.0.1:3010`; Studio prints its private session link. Keep that link
private. Stop only these processes after review. Website guide search is local search,
not an AI chat. Opening the example/inspecting/exporting requires no Docker. Running
the fixture requires local Linux Docker and explicitly preparing its test image;
running a managed model additionally requires reviewed weights/images, consent and
adequate resources. Neither happens on opening a page.

## Human review — observations intentionally blank

| Participant | Independent tasks | Actual observations |
| --- | --- | --- |
| Owner/nontechnical participant | Explain Furnace; find the example and results; distinguish recorded demo, deterministic fixture and real inference; explain a result's limitations; identify the next action. No Docker installation required for comprehension review. | |
| Unfamiliar developer | Determine prerequisites; inspect/export a kit; execute the fixture only if Docker is available; identify the managed versus existing-server paths and arbitrary-architecture limitation. | |

Record task success, confusion and exact words after participation. Label a guided session
assisted; automated browser success cannot fill these cells. The smallest remaining native
onboarding test is a fresh Windows user/profile with no Furnace/uv cache: install Python
3.12 and uv, extract the reviewed ZIP, follow its README, inspect/export the example, stop
and restart with preserved data and a rotated private link. Record prerequisites and all
commands actually executed; optional Docker/model tests are separate.

## Remaining gates and limits

- Human observations and native file-picker behavior remain unverified.
- Historical model records cite `0bf926f`; they are not new inference evidence for this
  candidate. No new weights, GPU experiments or live GitHub execution were performed here.
  Older PR-body claims without committed matching receipts were not adopted as evidence.
- Real-model validation on the final integrated build and target hardware remains a release
  gate. Shared artifact stores across independent workspaces, multi-user hosting, long soak,
  other host operating systems and arbitrary research adapters have no new verification.
- Billing, cloud provisioning, installers and deployment remain inactive/outside this work.
  Keep the combined PR draft until review and owner feedback; merging it needs approval.
