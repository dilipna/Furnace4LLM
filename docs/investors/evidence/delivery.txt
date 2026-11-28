# Local MVP delivery — deadline December 4, 2026

Owner-confirmed scope: **local MVP and private demonstration by Friday, December 4,
2026, end of day (America/New_York)**. Furnace remains a researcher infrastructure
platform with the free kit and Studio; documents is an example application. Both
journeys require installed acceptance. Keep the theme. The $20/month
plan is **Coming later**, with [hosted-service-design.md](hosted-service-design.md)
as its proposal. No public subscription, billing, accounts or internet-facing service
is included in this deadline.

Merges are conditionally approved only after Dilip reports a successful clean-account
install and each exact head is green. Publication needs a separate message from him
naming the final installer's exact SHA-256. No merge or publication has happened here.

## Provisional preview — not final dual-journey acceptance

`Furnace-0.1.0-9598d6d83beb-windows-x64.exe`, exact source
`9598d6d83beb25f7a372d6bf3f1299f4e9e7c5b3`, is an unsigned preview.
[Exact artifact and installed acceptance](installer-verification/candidate-9598d6d/README.md).
9598d6d has installed Studio acceptance only. Its document journey has **not** been
accepted on the installed bytes. Researcher Studio remains the product front door;
the document example stays accessible without changing that positioning.
After final source integration, build one new frozen installer and accept **both**
private documents and Studio Qwen/Granite on those exact bytes. Historical/source/
scripted document checks cannot substitute for installed real-model acceptance.

| Deliverable | Executed evidence | Boundary |
| --- | --- | --- |
| Document example journey | Final installed acceptance outstanding | Summary/question, correctness against the source, receipt/limits, protection and clear/navigation must be exercised on the final binary |
| Researcher website and Studio | CI-built site; download/hash, navigation, mobile/theme and installed home | Local preview; public hosting remains recorded-only |
| Assessment and free kit | Actual export → browser import → API save → re-export; installed UI ZIP download | Metadata inspection is not model execution or compatibility |
| Model serving and security controls | Exact installed Qwen and Granite CPU journeys | Two pinned recipes on one Windows/Docker machine |
| Evaluation and reproducibility | Qwen 11/12, Granite 7/12 quality rules; both 12/12 repeat/relaunch output equality | Wrong answers remain; equality is not correctness |
| Monitoring, recovery and export | Container failure, explicit restart, hard Studio crash/reopen, metrics, manifest export | Single-user local operation; no remote alerting or hosted failover |
| Self-contained Windows installation | Current-account install, bundled interpreter, application PATH without developer tools, uninstall | Independent account, SmartScreen and interactive choices still need people |

Custom models require a reviewed adapter/dependency image or compatible local server
and task-specific cases. Folder inspection does not automatically support an architecture.
This candidate has fresh CPU acceptance; earlier GPU records keep their original source.

## Remaining delivery gates

| Gate | Done criterion | Who |
| --- | --- | --- |
| Independent install | Exact verified candidate opens, inspects/exports and reopens in a clean Windows account; record actual errors/assistance | Owner/pilot participant |
| Comprehension | Explain purpose, free/proposed service, fixture/inference, requirements and next action without implementation coaching | Owner and unfamiliar participant |
| Interactive retention | Observe agreed keep/delete choices in a test account; never delete live project data for the test | Owner/participant |
| Linux gate | Hosted Ubuntu CI on each exact head is accepted for this release; retain the local diagnostic separately | Maintainer; do not change Docker Desktop settings |
| Distribution review | Review notices, draft policies and unsigned-preview disclosure; accept or identify changes | Owner |
| Integration | After Dilip's successful-clean-account report, integrate #18 → #19 → #20, then #15/#16; preserve ancestry, retarget and verify exact green heads; keep main green | Conditional owner approval already given |
| Final frozen installer | Rebuild from final source, record full SHA-256, and accept installed private documents plus Studio Qwen/Granite on the same bytes; any rebuilt replacement repeats both | Maintainer, with human checks separate |
| Publication | Separately approve the exact artifact/hash and recorded-only site after selected gates pass | Owner explicit approval |
| Future operated service | Proposal only; not a December 4 release gate or implemented offering | Coming later |

[Today's clean-account checklist and Sunday's participant packet](../operations/pilot-2026-11-29/README.md).
No actual pilot feedback has been supplied. Automation cannot fill these fields.
The original November 24 walkthrough is unchanged.

## Engineering checks

- **Hosted Ubuntu CI is the Linux gate for this release**, as explicitly accepted
  by the owner. Tests/thresholds remain unchanged. The local Docker-contained Python
  runner's loopback limitation remains a [retained diagnostic](local-linux-verification/README.md),
  not a pass and not a blocker requiring Docker Desktop changes for this release.
- Frozen-candidate [Python/web/image](https://github.com/dilipna/Furnace4LLM/actions/runs/46040961684),
  [Windows](https://github.com/dilipna/Furnace4LLM/actions/runs/46040961559) and
  [saved evidence](https://github.com/dilipna/Furnace4LLM/actions/runs/46040961640)
  checks are separate from checks on later documentation/verification heads.
- If the compiled candidate changes, repeat the installed-interpreter procedure in
  [Windows operations](../operations/windows-download.md#real-installed-model-validation).
  Use new record filenames and retain failures. Include installed real-document
  acceptance as well as both Studio recipes. Keep bytes, checksums, metadata,
  receipts and website identity together; never relabel an older acceptance run.

The earlier Linux Node-bootstrap `0-alpha` error is historical. A fresh Pyright
1.1.414 probe succeeded on 2026-11-27 but automatically installed Node 26.13.1,
unlike hosted Node 24. The local runner now supplies Node 24 from its existing Node
image. This fixes toolchain/test parity, not a reproduced current bootstrap failure.

## Freeze rule

Finish review, onboarding, final-source rebuild and same-byte dual acceptance before
optional features. Keep the theme. Do not add billing, accounts, internet-facing
infrastructure, new adapters, GPU experiments or automatic updates for this deadline.
Publication stays blocked until the separate owner message names the accepted hash.
