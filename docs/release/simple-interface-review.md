# Simple public website and local Studio — local review

No deployment or release publication. The redesigned public website is not yet the
hosted website. The local Studio is a separate application, not an inference service
embedded in the public site.

## Source and dependencies

PR #8 merged with normal merge commit `7911ffbcc8dfac53b36de712cc525bf9d3c62da7`
after explicit owner approval of its unchanged `b004e7f` head. PR #9 subsequently
merged through concurrent repository work, at main
`9e29aee0ec8837ff1f2e8727126e22076655d998`. Its additional recovery-lock correction
is preserved. This branch does not overwrite either merged branch.

`design/simple-interface` combines that main, the preserved website work at
`07ccfff90f025b9452a603be0a517c20deeefcef`, and local startup/CI corrections.
Those corrections remain separately reviewable on `fix/studio-startup-ci` at
`e582deaa04c02011c979cf114677f221f2a81def`; neither new branch has been published.

## What changed

- Public homepage: small sidebar, three starting points, working local guide search
  and expandable explanations. Search does not call an LLM.
- `/start`: three setup steps, self-reported prerequisites, copy success/failure
  handling, source commands and explicit fixture/connector limitations.
- `/research`: preserves the original technical homepage and its historical measurements.
  `/demo` remains explicitly recorded. Plans describe the free preview and inactive
  planned $20/month service, with no simulated checkout.
- Studio: simple welcome, expandable folder entry and infrastructure assessment,
  plain tab labels, and a message-oriented local-server page. Connection settings,
  saved-case execution and attempt history remain available in expandable panels.
  Consent, identity fencing, raw-data boundaries and execution limits are unchanged.

## Reproduce locally

Prerequisites: Git, Python 3.12, uv; Node 24 and pnpm 10.28.2 for the public site.
First installation needs network access. Docker is optional for Studio inspection,
export and HTTP connection; the deterministic infrastructure fixture needs local
Linux-container Docker. Real inference needs a separately operated compatible server.

From this branch's repository root, in separate terminals:

```powershell
pnpm --dir apps/web install --frozen-lockfile
$env:NEXT_PUBLIC_RECORDED_ONLY = "true"
pnpm --dir apps/web dev --hostname 127.0.0.1 --port 3008
```

Open `http://127.0.0.1:3008`. For Studio:

```powershell
uv sync --frozen
uv run furnace studio --no-browser
```

Open the private session link printed by Studio; keep it out of screenshots and logs.
These source commands are not a native installer. Use Ctrl+C to stop each preview.

Automated browser verification uses disposable workspaces, isolated headless browser
profiles and an authored local HTTP server, not a learned model or the user's tabs:

```powershell
uv run python scripts/verify_simple_interface.py --site-url http://127.0.0.1:3008 --browser-channel chrome --output interface-results.json --screenshots interface-screenshots
```

Requires installed Chrome, or omit `--browser-channel` after installing Playwright's
Chromium. Clipboard checks stub the browser API; they do not verify the OS clipboard.
The browser receipt records its source commit and whether the source was dirty.

## Evidence boundaries

The separate corrections commit `e582dea` passed the full local Linux verifier:
619 Python tests, lint/format/import boundaries/types, Postgres migrations, Web
(including 18 Studio state tests), normal and recorded-only builds, and API image
build/import. The local Python runner used the existing preinstalled-Node toolchain
image because its Node download bootstrap failed. Repository CI was not changed to
use this workaround. This is local Linux evidence, not hosted CI for this UI branch.

An earlier interrupted combined run had four failures in progress output but lost
its tracebacks when the Docker daemon disappeared. It is not reported as passed;
the subsequent isolated serial run above completed. No thresholds were relaxed.
Earlier combined ZIP verification at `0828912` and historical GPU measurements are
separate evidence, not new UI or model-inference results.

Current interface verification results are recorded below after running the checks.

## Human review — leave observations blank until participation

Open the public preview first; a nontechnical participant need not install Docker.
Record whether the session was independent or assisted. Do not count automated browser
checks as human understanding.

| Participant | Tasks | Actual observations | Assistance |
| --- | --- | --- | --- |
| Owner / nontechnical role | Explain Furnace's purpose; find a starting point; inspect the recording; distinguish a fixture from inference; explain one limitation. | | |
| Unfamiliar developer | Determine prerequisites; open Studio; inspect/export the example; identify the real-model limitation; execute the fixture only if Docker is available. | | |

For each task, record what was said/done, whether help was needed, and where the person
became stuck. If the owner fills both roles, report one participant, not two independent
participants. Guided observation is assisted evidence.

The smallest outstanding clean-environment onboarding test is a fresh supported OS
profile with Git, Python 3.12, uv and network access, an empty uv cache and no preexisting
Furnace workspace: clone an identified reviewed commit, run the documented source
commands, open the printed private link, create the guided example, export a valid kit,
stop and reopen Studio to confirm persistence. Docker and a GPU are not prerequisites
for this test. Expect no model execution, source mutation or paid provisioning. Cached
developer-environment success does not establish fresh-profile onboarding. macOS remains
unverified; native Windows file-picker selection also remains unverified because the
computer-use helper could not establish the browser URL safely.

Before release: review and publish the local corrections/UI branches with approval,
obtain exact-head hosted checks, complete human/fresh-profile onboarding, and separately
approve deployment. Model support needs an identified real server and reference outputs;
no new model/GPU run or managed provisioning was performed here.
