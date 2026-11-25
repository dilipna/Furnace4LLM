# Clean-account Windows installer check

Owner exercise; observations are blank until performed. Budget about 10 minutes once
the separate Windows account and Docker (if testing deletion) are ready. Account setup,
Docker installation and model downloads are outside that timebox. Use synthetic text only.
Do not change the November 24 walkthrough sheet.

## Prepare

1. In Windows Settings > Accounts > Other users, create a separate **standard local user**.
   Sign out and sign into it; do not reuse your developer account. Creating an account
   may require administrator approval; running Furnace should not request elevation.
2. Open the existing preview at http://127.0.0.1:4010 on this same machine. Keep the preview
   server running in your original account (Switch user rather than signing it out).
   Check the source/build ID in the download details before proceeding.
3. Download the executable through the page. In PowerShell run
   `Get-FileHash -Algorithm SHA256 -LiteralPath "$env:USERPROFILE/Downloads/FILE.exe"`,
   substituting its actual filename. Compare the **entire** hash with the page and that
   build's SHA256SUMS. Record both, not just the first eight characters.
4. Record the Windows version, browser, installer version/source, size and hash. Capture
   any SmartScreen/unknown-publisher dialog verbatim. Do not disable security controls.
   If policy blocks installation, stop and record the block rather than bypass it.
   A localhost download may not receive Mark-of-the-Web; **no warning is not evidence
   of a signed installer or of the future public-download SmartScreen experience**.

## Install, explore, quit (about 5 minutes)

- Run the installer. Record install location and whether an admin prompt appeared.
- Check Start and the selected desktop shortcut. Open Furnace: record whether a console
  flashed, whether the app window appeared and whether Studio opened automatically.
- Check the Docker message. Furnace must not install or start Docker silently. With
  Docker unavailable, the guided example's metadata and export should still work.
- Open the guided example, inspect its cases and export a kit. This does **not** run an LLM.
  Keep the export and a synthetic project folder outside the app/workspace directories.
- Close the browser: Furnace should remain running. Quit via the app window; reopen from
  Start. Record any workspace-busy error (none is expected after a completed Quit).

## Uninstall: test keep, then delete (about 5 minutes)

1. Quit the app. Uninstall from Windows Settings > Apps. Answer **No** to optional
   cleanup. Record dialogs, confirm app/shortcuts are gone, then reinstall the same file.
   The guided project record, external project folder and exported kit should remain.
2. Quit again. With Docker Desktop running Linux containers, uninstall and explicitly
   approve owned-resource cleanup, then record deletion. Approve weights/images only
   if you intend to remove this account's default Furnace cache; no model download is
   required for this test. Existing cleanup must retain external folders/exports.
3. Reinstall once more to inspect the result: deleted project records should be absent;
   your external project folder and export should remain. Quit and uninstall keeping
   data if you want to remove this final test installation.
4. If Docker is unavailable or cleanup reports incomplete, data retention is expected.
   Record **delete not verified**, not a successful deletion. Custom artifact stores and
   model folders are not installer-owned and should remain.

## Observation sheet — fill with actual observations

| Field | Actual observation |
| --- | --- |
| Date / Windows / browser / account type | |
| Installer filename / version / source / bytes | |
| Expected full SHA-256 / downloaded full SHA-256 | |
| SmartScreen / Mark-of-the-Web / policy outcome | |
| Admin prompt / install location / shortcuts | |
| Console / app window / automatic browser launch | |
| Docker message / example / export | |
| Quit / reopen / workspace ownership | |
| Keep choices / retained records and external files | |
| Delete choices / cleanup warnings / removed records | |
| External project folder and export preserved | |
| Screenshots / errors / assistance received | |

Use screenshots with session URLs, private paths and personal content hidden. Keep negative
outcomes. This checks installation and retention; it does not replace the independent
usability walkthrough, real-model evidence or a future public-download test.

## Applying the existing walkthrough to the installer

The Studio tasks still apply. Launch from Start instead of cloning or running a CLI;
there is no session link to copy. Missing Docker does not block inspection/export, but
fixture/model execution still needs Linux containers. Load the reference suite **before**
starting a model because it replaces cases. Closing the browser is not Quit. Crash injection
may require facilitator assistance and should be labelled assisted. Product-direction work
on a separate branch is not part of the installed #18 walkthrough. No document drop or
privacy-receipt task applies to this installer yet.
