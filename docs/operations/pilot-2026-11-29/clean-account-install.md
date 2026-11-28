# Clean-account Windows install — owner/tester checklist

Allow approximately 20–30 minutes after account/setup preparation; downloads are extra.
Use a separate standard Windows account with no previous Furnace installation. Record
if this is an existing machine with developer tools; a clean account is not proof of
a clean machine. Do not test deletion in an account holding valuable Furnace data.

## 1. Obtain and identify the preview

- Ask Dilip for the exact installer and SHA256SUMS. The localhost preview only works
  on Dilip's computer while its server runs. Use a private file transfer elsewhere.
- Current provisional file: `Furnace-0.1.0-9598d6d83beb-windows-x64.exe`.
- Expected SHA-256: `8fdb61c18526a811952edfe3f8aefb90735df22f6a69d2251aa4a7600fc9a02d`.
- In PowerShell, replace the example path with the downloaded file's full path:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\path\to\Furnace-0.1.0-9598d6d83beb-windows-x64.exe'
```

Compare all 64 characters. Stop on mismatch. A checksum checks bytes, not publisher
identity. This preview is unsigned. Record SmartScreen/unknown-publisher/policy text;
do not disable protection or bypass an organization policy. A private/local transfer
may lack Mark-of-the-Web: no warning does not prove a future public download is trusted.

## 2. Install and open

1. Run the installer, note its location and any administrator prompt. The app should
   not need Git, Python, uv or a terminal for normal use.
2. Check Start and any chosen desktop shortcut. Open Furnace; note the app window,
   automatic browser opening, unexpected console windows and any error.
3. In 9598d6d the initial screen is researcher Studio. Reach documents through
   **Example application: documents**. Researcher Studio remains the product front
   door; report the actual interface.
4. Check the Docker/setup message. Keep Docker settings unchanged. Inspection/example
   metadata and starter-kit export can work without Docker. Real document answers and
   model operations need Docker with Linux containers and sufficient resources.
5. Open the guided infrastructure example and export its kit. This is a deterministic
   fixture, not an LLM. Confirm the ZIP opens and save it outside the application folder.

## 3. Exercise the two journeys, when Docker is available

- **Documents:** open `sample-document.txt` from this packet. In **Model & setup**
  choose the CPU/faster Qwen2.5-1.5B option and CPU unless Dilip supplies another
  explicitly identified test configuration. Approve preparation/start deliberately.
  Summarise, ask about the fee/deadline, compare with the source, inspect the visible
  receipt and its details, then use **New conversation** to clear. Record wrong,
  missing, timed-out or truncated answers; a visible answer is not automatically a pass.
- **Studio:** use the participant sheet's developer tasks to run Qwen2.5-0.5B and
  Granite sequentially, inspect results and export. Stop each server explicitly.
- Record prerequisites/downloads that block execution separately from install results.
  A successful install alone does not accept either real-model journey.

## 4. Quit, reopen and test retention in this test account

1. Close the browser: observe whether the Furnace app remains running. Quit from its
   app window, reopen from Start and check saved project identity/settings. No model
   should silently download, restart or reconnect merely because the app reopens.
2. Quit, uninstall interactively, decline optional cleanup, and record the choices.
   Reinstall the same file. Check saved workspace records, external folder and kit.
3. Only in this disposable account, and with Docker available, quit/uninstall again
   and explicitly approve owned-resource/record cleanup. Record each actual prompt;
   remove weights/images only if deliberately agreed. External model folders and
   exports must remain. Reinstall to inspect whether the selected records were removed.
4. If Docker or cleanup is unavailable, mark deletion **not verified/blocked**, not passed.

## Report actual observations

| Item | Actual observation / evidence |
| --- | --- |
| Date, Windows/browser, account type and prior tools | |
| Filename, source, expected and actual full SHA-256 | |
| Transfer method, SmartScreen/policy outcome | |
| Install location, admin prompt, shortcuts, launch | |
| No-Docker inspection/example and actual ZIP export | |
| Documents: model/device, answer errors, receipt, clear | |
| Studio: models/device, evaluation, export, stop | |
| Quit/reopen, identity and unwanted automatic actions | |
| Keep/delete choices, warnings and retained external files | |
| Assistance, blockers and screenshots | |

Hide session URLs, personal paths and private content in screenshots. Keep failures.
Send Dilip the observations and state **pass / failed / blocked / partially tested**
for installation, each journey and retention separately. Only Dilip's subsequent
successful-clean-account report satisfies the owner's merge condition. This sheet
does not authorize a merge or publication, or replace final same-byte dual acceptance.
