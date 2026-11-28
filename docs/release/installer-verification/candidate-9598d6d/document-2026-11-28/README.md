# Installed document CPU acceptance — November 28, 2026

Actual new execution on the unchanged provisional installer from source
`9598d6d83beb25f7a372d6bf3f1299f4e9e7c5b3`, SHA-256
`8fdb61c18526a811952edfe3f8aefb90735df22f6a69d2251aa4a7600fc9a02d`.
Unsigned/unpublished. This closes the missing developer document check on these
provisional bytes; it does not accept a future final rebuild or a clean user account.

A new dedicated QA directory outside all checkouts was installed after checking no
Furnace registration existed. Installed identity and registration matched. Both tests
used the installed interpreter/API; application code was not monkeypatched. Shared
pinned weights/images were cached and preparation reverified weights. This is one
Windows 11 + Docker Desktop machine, CPU only; unrelated workloads were running.
No fresh GPU, arbitrary researcher architecture or timing comparison is claimed.

## Actual results

| Execution | Outcome | Evidence |
| --- | --- | --- |
| Real installed Qwen2.5-1.5B CPU suite | All 42 planned cases completed; 37 rule passes, 5 failures, no unscored cases; clean shutdown | [Raw record](everyday-cpu.json), [exact suite](suite.json) |
| Eight fixed document attacks | 8/8 rules passed in this run; not general injection resistance | Same raw case records; no attacks omitted |
| Installed browser journey | PDF import/extraction, summary, deadline, missing-info and invoice-injection answers; all four explicit task rules passed | [Final browser record](browser-3/record.json) |
| Visible receipt and set-aside warning | Checked receipt from actual model responses visible with details closed; details explain scope; set-aside visible before inference | Actual screenshots below |
| Clear/reload | Source and answers cleared; reload kept model binding; no browser errors | Final browser checks |
| Stop and subsequent request | Confirmed stop via UI and API state; plan refused HTTP 409, no inference request sent and no restart | Final browser `stopped_response` and checks |
| Installation and uninstall | QA registration/runtime removed, shared weights retained, no Furnace-managed containers left | [Install](install.json), [uninstall](uninstall.json) |

The suite's recorded SHA-256 matches archived bytes from the exact candidate Git
blob. The supplied suite and output count both equal 42. The main suite's rules and
scorer were unchanged; none of its five failures was retried for a preferred score.
The browser's four synthetic task rules are separate acceptance tasks, not additions
to or replacements for the 42-case score. Repeated browser attempts below were needed
to correct test instrumentation and preserve their actual outputs.

## Five suite failures — retained

- Simplify wording: fee correct, date expressed in words instead of the required exact
  string. A rule failure is not automatically a factual error.
- Bank suffix: said the account suffix was unavailable despite the source containing it.
- Email actions: mixed up ownership/deadline details.
- Form reference/deadline: reference correct, date expressed in words; strict rule failed.
- Long form question: repeated trusted instruction text rather than answering the facts.

These last behavior errors are real model limitations. Small synthetic examples passing
is not proof every document answer is correct. Check critical facts against sources;
privacy/isolation checks and output quality remain separate.

## Test failures investigated, preserved, then corrected

- [Browser attempt 1](browser-1/record.json): real summary returned; harness selected
  both the outer receipt summary and its nested technical summary. Fixed the selector
  to the direct child. This was test code, not an application fix.
- [Browser attempt 2](browser-2/record.json): four task rules and stop/clear/reload checks
  passed; harness waited for `/answer-stream` after stopping. Source inspection showed
  the actual app refuses earlier at `/plan`. Corrected the assertion to observe that
  real refusal and verify no inference request/restart. No application code changed.
- [Browser attempt 3](browser-3/record.json): complete acceptance passed. Earlier records
  and their model outputs remain; no result was overwritten or promoted to a pass.

## Real screenshots

![Actual CPU document summary with visible receipt](browser-3/summary.png)

![Actual set-aside protection before inference](browser-3/set-aside.png)

![Actual invoice answer and visible warning/receipt](browser-3/injection.png)

![Actual refusal after the model was stopped](browser-3/stopped-model.png)

## Reproduce on an explicitly chosen QA installation

These are developer checks, not instructions for a normal user's installation.
Dependencies are the repository's existing test environment, Playwright Chromium and
working Linux-container Docker. No Docker settings changes or new dependencies.
Quit an app using the chosen installation first. Use a new output filename/directory.

```powershell
$app = 'C:\path\to\installed-QA-Furnace'
$installer = 'C:\path\to\Furnace-0.1.0-9598d6d83beb-windows-x64.exe'
& (Join-Path $app 'runtime/python.exe') -I scripts/validate_everyday.py --installed-build $app --model qwen2.5-1.5b-instruct-q4_k_m --accelerator cpu --out dist/my-installed-document-cpu.json
.venv/Scripts/python.exe scripts/accept_installed_documents.py --app $app --installer $installer --expected-sha256 8fdb61c18526a811952edfe3f8aefb90735df22f6a69d2251aa4a7600fc9a02d --out dist/my-installed-document-browser
```

Optional `--browser-executable` selects an existing Chromium; the actual run used the
existing test browser. The application child has developer Python/Git/uv removed from
PATH, retaining Docker and Windows system tools. Injected PYTHONHOME/PYTHONPATH values
are ignored by its installed `-I` interpreter. Preparation and start are actual UI
approvals. A private test pipe holds the launch session token; it is not archived.

Local relevant checks: everyday API tests 37 passed; JS model-selection tests 6 passed;
new harness Ruff/format and explicit Pyright passed. These are Windows checks, not
Linux CI. Hosted checks on the resulting branch head are separate from this binary.

Still pending: independent install, SmartScreen, interactive keep/delete, human
comprehension and pilot; integrated-source rebuild and both journeys accepted again
on its exact bytes. No merge, publication, deployment or SaaS service is implied.
