# Windows installer and download-site preview

Status: **draft, unpublished**. Main and the existing recorded-only website are not
changed by this branch. PRs #15/#16 and the November 24 walkthrough sheet are untouched.

## End-user journey

1. On the download page, review the OS, version, byte size, date and SHA-256 generated
   from the actual installer. macOS/Linux installers are not built or verified.
2. Verify the checksum if desired, then run the unsigned Windows x64 installer.
   Furnace installs for your account and registers shortcuts and a normal uninstaller.
   No Git, Python, uv, administrator prompt or terminal is required for app use.
3. Open Furnace from Start. Its small app window starts Studio on a private, OS-assigned
   loopback port and opens the default browser. The session token stays in memory;
   there is no session link to copy or token file.
4. The read-only first-run check explains missing Docker or Linux containers and links
   to Docker's official download. Furnace never installs Docker. Inspect metadata,
   explore the guided example and export a kit without Docker.
5. For Qwen: select and save the CPU recipe, approve preparation, load the reference
   suite **before Start** (it replaces cases), start, ask, then evaluate. A rule score
   is not semantic quality. Preparation/start times are not a five-minute guarantee.
6. Closing the browser does not quit Studio. Use Quit Furnace or close its app window;
   this waits for the existing lifespan cleanup and releases the workspace lease.

## Build from clean source (developer only)

The build machine needs Git, uv, Windows x64 and the pinned compiler; the installed app
does not. Runtime dependencies are exported from `uv.lock` with hashes and installed
into a private CPython 3.12.13 runtime. Inno Setup 6.4.3 is checksum-pinned; its license
permits free commercial use. Runtime/dependency license files are retained in the app. The builder also copies
Furnace's root MIT notice to the installed `LICENSE`; the developer ZIP contains it
at its root. Installed smoke checks require exact notice bytes. See the
[reproduced notice omission and correction](../release/distribution-notices/README.md).
This does not replace the owner's broader distribution review.

```powershell
uv python install 3.12.13
uv sync --frozen --python 3.12.13
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_compiler.ps1
uv run python scripts/build_windows.py --iscc dist/build-tools/inno/ISCC.exe
uv run python scripts/package_release.py --windows dist/windows/installer.json
```

The builder refuses dirty source, rechecks source after compilation, reads versions
from project metadata, and records source, wheel hashes, Python/compiler versions,
installer size/digest and Authenticode status. The release packager refuses stale
source/version, unsafe paths and changed bytes before replacing output. Signing is
optional via `--sign-command`; the compiler must produce valid Authenticode when
requested. Use a certificate store/hardware key, never a password in command arguments.
No signing credentials or signing service are configured or exercised here.

This is a repeatable pinned-input CI recipe, **not established byte-for-byte
reproducibility**: compiler/PE timestamps and build paths can affect bytes. Always verify
the checksum for the exact artifact. Do not relabel an older installer as a newer build.

## Preview locally, with real artifacts

```powershell
uv run python scripts/stage_download.py
uv run python scripts/export_release_notes.py
pnpm --dir apps/web install --frozen-lockfile
$env:NEXT_PUBLIC_RECORDED_ONLY='true'
pnpm --dir apps/web build:static
uv run python scripts/preview_site.py --port 4010
```

Open <http://127.0.0.1:4010>. The preview serves the actual executable from its local
download folder. No binary is committed or uploaded to a public release. The page
checks metadata against the bytes at build time; absent metadata shows build status,
not a fake download. Build date is labelled **Built**, not Released. Release notes
come from public GitHub release data and omit drafts.

`preview_site.py` supports clean exported URLs, the real 404 page, text compression
and immutable caching only for hashed Next assets. It is loopback-only and has no API
proxy. The earlier Guard video directory coexists with `/demo.html`; the page takes
precedence over directory listing. Earlier tools remain under Earlier work, preserving
their measurements and URLs without competing with Studio in the main navigation.

## Verification commands

```powershell
uv run pytest -q apps/api/tests/test_desktop.py apps/api/tests/test_desktop_cleanup.py packages/furnace/tests/test_windows_release.py packages/furnace/tests/test_download_preview.py
node --test apps/web/lib/download.test.mjs
uv run python scripts/smoke_installed.py --app PATH_TO_INSTALLED_APP --out dist/installed-smoke.json --screenshots dist/captures
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_windows_window.ps1 -AppDir PATH_TO_INSTALLED_APP -Installer PATH_TO_INSTALLER -Screenshots dist/captures
uv run python scripts/verify_download_site.py
```

Install Playwright Chromium on the build/test machine with `uv run playwright install
chromium` (not required on users' machines). The Windows CI workflow starts with a fresh
Furnace installation and checks per-user registration, both shortcuts, actual native
windows, browser preflight/example/export, Quit/lease release, uninstall and default
data retention. Its child process has Git/Python/uv removed from PATH and invalid
PYTHONHOME/PYTHONPATH to verify interpreter isolation. Hosted runners still have developer
tools globally: this is not a manual clean consumer-machine/SmartScreen test.

The regular hosted Ubuntu suite, type/lint/import checks, Web/Studio state tests,
API-image build and saved-evidence checks remain enabled. Windows CI artifacts contain
the executable, checksums, receipts, screenshots and unpublished static site. Tests do
not claim human comprehension, and no new GPU inference is implied.

## Real installed-model validation

Quit the installed app first. Start Docker Desktop with Linux containers yourself.
From this source checkout, use the **installed** interpreter so source/user-site imports
cannot replace the installed code:

```powershell
$app = Join-Path $env:LOCALAPPDATA 'Programs/Furnace'
& (Join-Path $app 'runtime/python.exe') -I scripts/validate_managed_model.py --installed-build $app --model qwen2.5-0.5b-instruct-q8_0 --accelerator cpu --out dist/installed-qwen-cpu.json
```

Use the test installation path instead when reviewing a custom install. The harness
checks interpreter/module ownership and attributes source to installed `build.json`,
not the harness checkout. It uses a fresh workspace and preserves failed outcomes.
Preparation failure is now recorded before aborting, instead of cascading into a
missing-container error. Model rule scores remain separate from operational checks.
Recorded trials belong to their exact installed build; a newer installer needs its
own acceptance run before publication. See [the evidence index](../release/installer-verification/README.md).

To make an actual, uncut local browser recording, with cached assets disclosed:

```powershell
uv run python scripts/record_installed_demo.py --app PATH_TO_INSTALLED_APP --out dist/installed-demo
```

This is automated real-model interaction, not an independent-user pilot. Installer and
launcher footage are separate real still captures. Failed takes remain separate; they
must not be labelled successful or overwritten to conceal failures. Publication still
needs approval. Tomorrow's owner walkthrough and its separate script are unchanged.

## Uninstall and retention

Quit Furnace, then use Windows Settings → Apps → Furnace → Uninstall. Default and
silent uninstall remove the app/shortcuts/registration and **keep data**. Interactive
uninstall asks separately about owned containers/networks, default verified weights/
pinned images and saved records/logs. It uses the existing cleanup implementation,
refuses a live workspace, and reports incomplete cleanup. Custom model folders, external
artifact stores and exports are not installer-owned. Empty workspace/lock directories
may remain. Docker must be available for confirmed optional cleanup.

## Unsigned preview and publishing gates

SmartScreen may identify an unknown publisher or show “Windows protected your PC.”
Do not disable protection. Check the complete SHA-256 with
`Get-FileHash -Algorithm SHA256 -LiteralPath PATH_TO_INSTALLER`; compare against
SHA256SUMS from the same build. A hash detects corruption, not publisher identity.
Organization policies may block unsigned software even when its checksum matches.

Before public release: owner reviews the actual preview, all exact-head checks pass,
the selected installed candidate passes Qwen CPU acceptance, software distribution
licensing and draft legal pages are reviewed, and manual clean-account installation/
SmartScreen/interactive data-retention behavior is checked. macOS/Linux installers,
automatic updates and publisher signing remain outside the verified Windows preview.

Only **after explicit approval**, these are the separate outward-facing commands:

```powershell
# PUBLIC GITHUB RELEASE — do not run during draft review:
gh release create TAG dist/release/* --repo dilipna/Furnace4LLM --title 'Furnace VERSION' --generate-notes
# Prepare the website only AFTER the exact reviewed release is public:
uv run python scripts/stage_download.py --published-tag TAG
uv run python scripts/export_release_notes.py
$env:NEXT_PUBLIC_RECORDED_ONLY='true'
$env:FURNACE_PUBLIC_SITE='true'
pnpm --dir apps/web build:static
uv run python scripts/check_pages_bundle.py
# WEBSITE DEPLOY — separate approval, existing free Cloudflare Pages project:
Push-Location apps/web/cloudflare
wrangler pages deploy ../out --project-name furnace --branch main
Pop-Location
```

Replace TAG/VERSION with the reviewed version; review the release-note preview first.
The deploy command assumes the owner's existing authenticated Wrangler installation.
No new account, domain, paid hosting, billing or waitlist backend is created here.

Cloudflare Pages has a [25 MiB per-file limit](https://developers.cloudflare.com/pages/platform/limits/).
The Windows installer exceeds it. Local previews serve the actual executable; public
builds link to an already approved GitHub Release asset, verifying its SHA-256 digest,
size and owned repository URL against the reviewed candidate. The staging command
never creates a release. The size gate rejects a local preview or oversized files
before deployment. No paid storage or new account is required. Public-link staging
has unit coverage with authored release metadata; it has not been exercised against
a newly published Furnace installer because publication is not authorized.

To stage the executed local recording before building the preview:
`uv run python scripts/stage_recording.py dist/installed-demo-reviewed`.
The media stays in ignored generated output; this does not publish it.
