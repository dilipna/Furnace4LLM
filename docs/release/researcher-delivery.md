# Researcher delivery checklist — 2026-11-27

This covers the deliverable Windows researcher application. The original product also
includes a proposed $20/month Furnace-operated service; that service is **not built**.
Completing the local checklist does not complete that offer. The owner's exact deadline
and local/private-demo versus public-service delivery target await confirmation.
Nothing here authorizes a merge, release, deployment or spending.

## Frozen candidate and evidence

`Furnace-0.1.0-9598d6d83beb-windows-x64.exe`, exact source
`9598d6d83beb25f7a372d6bf3f1299f4e9e7c5b3`, is an unsigned preview.
[Exact artifact and installed acceptance](installer-verification/candidate-9598d6d/README.md).

| Deliverable | Executed evidence | Boundary |
| --- | --- | --- |
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
| Full local Linux gate | Run on a Linux Docker host with reachable host-loopback networking; current Docker Desktop container topology is blocked | Environment prerequisite; do not skip serving tests |
| Distribution review | Review notices, draft policies and unsigned-preview disclosure; accept or identify changes | Owner |
| Integration | Approve reviewed #18 → #19 → #20; preserve ancestry, retarget children, obtain exact-head checks; keep main green | Owner approval, then maintainer execution |
| Publication | Separately approve the exact artifact/hash and recorded-only site after selected gates pass | Owner explicit approval |
| Operated service | Choose host/access scope, then implement authentication, operator controls, limits, backups/restore and security/recovery acceptance | Product decision plus engineering; not a publishing checkbox |

[Participant tasks and blank observations](../operations/researcher-preview-review.md).
No actual pilot feedback has been supplied. Automation cannot fill these fields.
The original November 24 walkthrough is unchanged.

## Engineering checks

- `bash scripts/ci_linux.sh` must exit zero on the committed tree: non-root Linux
  Python, migrations/full non-GPU suite, web tests/builds and API image. Its Node
  major and JavaScript tests now match hosted CI. A complete pass records the exact
  source commit in the repository's local pre-push receipt.
  The Python job needs host-loopback networking because serving tests use Docker's
  loopback-published relays. It now fails early if that path is unavailable and never
  writes a success stamp. On the current Docker Desktop setup, both bridge and host
  container probes refused a service that the Windows host reached with HTTP 200.
  Global Docker settings were not changed. Use a native Linux host or explicitly
  configure Desktop host networking when safe for other projects. Hosted Ubuntu
  results are separate, not a claim that this local gate passed. See the
  [retained failure and diagnostic](local-linux-verification/README.md).
- Frozen-candidate [Python/web/image](https://github.com/dilipna/Furnace4LLM/actions/runs/46040961684),
  [Windows](https://github.com/dilipna/Furnace4LLM/actions/runs/46040961559) and
  [saved evidence](https://github.com/dilipna/Furnace4LLM/actions/runs/46040961640)
  checks are separate from checks on later documentation/verification heads.
- If the compiled candidate changes, repeat the installed-interpreter procedure in
  [Windows operations](../operations/windows-download.md#real-installed-model-validation).
  Use new record filenames and retain failures. Keep bytes, checksums, metadata,
  receipts and website identity together; never relabel an older acceptance run.

The earlier Linux Node-bootstrap `0-alpha` error is historical. A fresh Pyright
1.1.414 probe succeeded on 2026-11-27 but automatically installed Node 26.13.1,
unlike hosted Node 24. The local runner now supplies Node 24 from its existing Node
image. This fixes toolchain/test parity, not a reproduced current bootstrap failure.

## Freeze rule

Finish review, onboarding and release gates before optional features. Keep the theme.
Do not add billing, adapters, paid infrastructure, GPU experiments or automatic updates
to make the checklist larger. If public managed service is selected for the deadline,
it needs its own implementation and acceptance scope; the free app cannot stand in for it.
