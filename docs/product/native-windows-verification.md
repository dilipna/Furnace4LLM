# Native Windows installed-preview verification — 2026-11-16

Application source: `64798eb7d33e30cf779b7064e3b2b9231d42e1a1` (clean).
Verifier source: `65823ec0701835ac0c6128f4c02e03d8a13a96b4`.
The intervening commits change verification and documentation, not the application.

The same installed ZIP was exercised outside the checkout on native Windows and
in an isolated Linux container. SHA-256:

```text
405ad1c75b46a8022d0eb67078c60e7f454cd444e993e4abe52889e9f53f28bf
```

## New execution evidence

| Check | Native Windows | Local Linux container |
| --- | --- | --- |
| Python | 3.12.13 | 3.12.12, uid 10001, read-only root |
| Installation | Empty dedicated uv cache; existing user, Python and uv | Empty cache; no Docker CLI/socket in Studio |
| First install/start | 121.56 s | 118.12 s |
| Metadata, edits, kit export | Passed without Docker discovery | Passed without Docker discovery |
| Connector | 6 actual authored HTTP requests; explicit failure/retry | 16 actual authored HTTP requests; installed Chromium journey |
| Restart | Endpoint disconnected, two history identities retained, old token rejected | Same contract passed |
| Shutdown | CTRL_BREAK_EVENT; actual connection refusal and workspace byte-lock release | SIGINT; connection refusal, workspace reuse verified by restart |

Receipts: [Windows](verification/native-windows-64798eb.json) and
[Linux](verification/linux-platform-64798eb.json). Both are local execution, not hosted
CI. These first-start durations include dependency installation and launcher overhead;
they are neither model latency nor a controlled platform-performance comparison.
The HTTP server returns authored responses. No learned model, GPU or remote inference ran.

Linux Chromium 153.0.8010.12 additionally exercised case import, history, identity
fencing, explicit export, keyboard controls and synthetic persisted-pageshow recovery.
Actual browser BFCache use was not asserted. Windows verification used the installed
API; it did not exercise a native file chooser or a Windows browser.

## Corrections made during verification

An initial Windows harness restarted after the launcher exited but before the
workspace lock was released; restart correctly refused the still-owned workspace.
The verifier now requires the listener to refuse a connection **and** the workspace
byte lock to be available. It does not treat a timeout/reset as proof of shutdown.
The original 0.5-second Linux probe budget also falsely rejected closed Windows
listeners: a direct closed-port refusal took about 2.12 seconds on this host.
The Windows probe budget is now 3 seconds, with bounded overall waiting. Requests
explicitly bypass proxies and use loopback. These were verifier corrections, not an
application reliability fix. An earlier Linux invocation failed because Docker Desktop
was stopped; after starting the installed daemon, the final invocation passed.

## Repeat on Windows

Prerequisites: Windows, Python 3.12, uv, network access to the pinned Python packages,
and the locally built preview ZIP. Docker is not needed for this API-only check.
Run from an interactive PowerShell console so the child process group can receive
CTRL_BREAK_EVENT. The verifier creates a temporary install/workspace and removes
them; the receipt is retained at the chosen output path.

```powershell
$trialRoot = Join-Path $env:TEMP ('furnace-native-check-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $trialRoot | Out-Null
$env:UV_CACHE_DIR = Join-Path $trialRoot 'uv-cache'
$env:UV_TOOL_DIR = Join-Path $trialRoot 'uv-tools'
$env:UV_PYTHON_DOWNLOADS = 'never'
.venv\Scripts\python.exe scripts/verify_studio_onboarding.py dist/furnace-studio-preview.zip --expect-empty-cache --connector --output "$trialRoot/result.json"
```

Use an already provisioned repository Python environment to invoke the verifier.
Do not use `uv run` here: it may populate the dedicated cache before the script
checks it. The direct Python invocation above is the tested command.

Restore the previous process environment values after testing. Do not reuse the
cache for a second `--expect-empty-cache` run. This test was executed with a PTY;
headless Windows service/CI signal delivery is not established.

## Remaining release gates

This closes the existing-user native Windows installed-API verification gap.
It does not establish fresh-profile onboarding, human comprehension, native
file-picker usability, macOS support, other browser engines or real-model support.
The smallest remaining clean-environment check is a fresh Windows user profile
with only Python 3.12 and uv installed, downloading/extracting the same ZIP and
launching it from outside a checkout with Docker absent. Expected: inspect metadata,
save/reopen a workspace and export a kit; fixture execution must explain its Docker
prerequisite. Record actual commands, errors and elapsed setup time. Leave human
observations blank until the owner or participants perform the tasks in
[the Studio guide](studio.md#human-review-no-participants-yet).
