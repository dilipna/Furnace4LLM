# Native Windows installed-preview verification

## Scope

This is automated execution under the existing Windows user, not a fresh machine/profile
or human usability study. Windows 11 build 26300, Python 3.12.13 and uv 0.11.23 were used.
The checkout's wheels were installed by the generated launcher from an extracted archive
outside the checkout with a separate initially empty UV_CACHE_DIR. Existing Python/uv,
OS, user profile, network configuration and Docker installation were reused. macOS and
fresh native-user onboarding remain unverified.

## Original archive and confirmed defect

The original furnace-studio-preview.zip from source
34748999f5f0b14b0cefbf09cd38af05b4562f80 has SHA256
43fcdc36c3a1bcaa9e1d98a7052a3ed6bb801cb0cc53224015f597358aff8909.
The initially empty cache installed 57 packages. Real loopback HTTP checks passed startup,
metadata example creation, contract editing, six-file kit/export provenance, module MIME,
the real-model limitation guide, invalid-token rejection (401), foreign-origin rejection
(403), restart persistence and old-token rejection (401). No fixture/model/GPU execution
was performed. Docker readiness was not the subject of this test.

On Ctrl+C, Uvicorn completed lifespan cleanup and exited its child process, then re-raised
KeyboardInterrupt through Studio and printed a traceback. This was reproduced twice
with the original installed archive. The PTY PowerShell invocation reported exit 1;
that wrapper result is not a separately isolated launcher exit-code measurement.

Studio now handles only KeyboardInterrupt around server.run, after Uvicorn's cleanup.
A completed startup can return quietly; interruption before startup exits 130. Actual
startup failure and unexpected runtime exceptions still report failure. The generated
outer launcher already handles its own KeyboardInterrupt as exit 130; this change does
not promise every enclosing shell reports exit 0. It does not alter runtime isolation,
worker cleanup, retries, evaluation identity or performance acceptance.

Four boundary regressions reproduced two failures before the correction and passed
afterward: interrupt after startup, interrupt before startup, failed startup without an
exception, and an unexpected server exception. Installed-package Ctrl+C and exact rebuilt
archive/source/hash evidence are recorded in PR #7's Windows verification section.
The old archive and Linux receipt are retained and must not be relabeled fixed.

## Repeat the bounded Windows check

Prerequisites: uv on PATH, installed Python 3.12, registry access and the exact reviewed
ZIP. PowerShell's default python may select another version; select the documented
prerequisite explicitly. Use new directories outside the checkout, not existing user
workspace/cache folders. Substitute the chosen ZIP and empty destination/cache paths:

```powershell
Expand-Archive -LiteralPath $bundlePath -DestinationPath $freshExtractedFolder
$env:UV_CACHE_DIR = $freshEmptyCache
$python312 = uv python find 3.12
Set-Location -LiteralPath $freshExtractedFolder
& $python312 launch.py --no-browser --workspace $freshWorkspace --port 8799
```

Open only the private loopback link. Never publish the session token. Open the example,
edit its contract and export the kit; verify project/configuration provenance says
execution not_run and model_inference false. Ctrl+C should complete application shutdown
without a Python traceback. Confirm the child exited, reopen the same workspace, confirm
metadata survives, and confirm the old session is refused. A fresh process prints a new
session token. Stop again and check no owned worker was left behind. Do not execute the
fixture during this metadata-only smoke. Local Linux-container Docker is a separate
execution prerequisite.

Do not delete shared model folders, global uv caches or unrelated processes as cleanup.
Retain only sanitized receipts. This procedure and the existing automated Linux smoke
do not establish human comprehension, native installers or real-model support.
