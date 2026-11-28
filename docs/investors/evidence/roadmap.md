# Furnace roadmap status (2026-11-17)

Status of the nine work items in the owner's remaining-work list. "Verified" means executed
and recorded in this repository; "proposal" means a written recommendation that needs an
owner decision; "blocked" names the decision or resource that is missing.

## 1. Integrate the completed code — done

- PR #8 (dependency-cache recovery): merged by the owner (`7911ffb`).
- PR #9 (local-server connection, history, case import): reviewed, one defect fixed before
  merge (`2d1d297`: shutdown recovery could rewrite a completed run as interrupted from a
  stale read; regression test added), merged as `9e29aee`.
- Combined result tested: local Windows 610 passed / 3 skipped; hosted CI on the merge with
  main 613 passed / 1 skipped (optional lab network), web, image and saved-evidence jobs passed.

## 2. Validate one real model — done for two models on one machine

- Pinned: llama.cpp b12004 images by digest; Qwen2.5 0.5B Instruct Q8_0 and IBM Granite 4.0
  H 350M Q8_0 (a Mamba-2/attention hybrid) by revision, size and SHA-256; a reference suite
  pinned by digest.
- Verified on Windows 11 + Docker Desktop (WSL2), RTX 3050 Ti Laptop 4 GiB, on CPU and GPU:
  inference, rule-scored evaluation, reproducibility (repeat, across a server relaunch, and by
  independent re-execution), a crash injected mid-evaluation, explicit restart, a hard Studio
  crash with recovery on reopen, export and stop; plus an interrupted and resumed fresh
  download. Results, hardware and limitations: [real-model-validation.md](../product/real-model-validation.md).
- Not verified: Linux or macOS hosts running a real model, other GPUs, larger models,
  concurrent users, long-running soak.

## 3. Furnace prepares and operates the model environment — done (local)

Prepare (pull pinned images, resumable verified download), start, readiness, stop, failure
detection, orphan recovery after a crash, and the adapter contract for other architectures
(engine adapter plus a Python adapter host for researcher code).
Contract: [managed-local-runtime.md](../product/managed-local-runtime.md).
Researcher-supplied adapters are offered in Studio ("Your own Python adapter"): pinned or
local image, read-only code folder digested by content, honest weights evidence; tested end
to end through Studio on real Docker with a deterministic test adapter. No researcher's own
model has been validated yet.

## 4. Infrastructure around the model — done for the local scope

| need | status |
| --- | --- |
| logs, metrics, health | operations log (structured, retention-bound, refuses content), server Prometheus counters, container resources, log tail, health states |
| resource limits, timeouts, recovery | container memory/CPU/PID limits without swap, request and evaluation budgets, server timeouts, explicit restart, crash recovery |
| secure configuration and secrets | per-launch key excluded from Studio database, logs and exports; passed in Docker environment and inspectable by Docker administrators |
| durable model/config/version records | pinned recipes, serving-manifest digest cited by each run, export of the manifest |
| reproducible runs with identified references | suite digest, sampling, manifest, weights digest and launch per run; automatic reproducibility comparison |
| quality beyond exact strings | normalized, contains, regex, numeric, choice and JSON-field rules |

GPU telemetry (memory, utilisation, temperature) is shown for NVIDIA launches; preflight
refuses launches Docker cannot satisfy (missing engine or GPU runtime, memory or CPUs above
Docker's limits) with actionable codes.

Not built: remote log shipping, alerting, encrypted local storage, semantic/LLM-judge scoring.

## 5. Managed service for the first one or two demo models — blocked on owner decisions

The local supervisor is the building block a hosted service would run per tenant, but no
hosted service exists. Before engineering it, the owner needs to decide:

1. **Hosting provider and region** (and whether the first demo is a single owner-operated
   GPU box or a cloud provider).
2. **Spending limit** for demo compute and storage.
3. **Who may access the demo** (invited researchers only is the recommendation).

Engineering that follows those decisions: authenticated multi-user access, per-tenant
isolation on shared hosts, storage and backups, update and cleanup procedures, a public
endpoint with TLS, and a demonstrated recovery drill. A design proposal mapping the verified
local components onto a hosted demo is in [hosted-service-design.md](hosted-service-design.md).

## 6. Subscription — proposal; billing and accounts inactive

Recommended definition of the $20/month plan for the demo phase (owner to accept or change):

| item | proposal |
| --- | --- |
| compute ownership | customer-provided compute by default (Furnace operates software on the researcher's machine or cloud account); Furnace-provided compute only for the 1–2 demo models, with a hard monthly cap |
| included Furnace-provided usage | the demo models only; a fixed GPU-hour cap per month (number to set once the hosting cost is known); requests beyond the cap refused, never billed silently |
| storage | weights of the selected demo models plus 5 GiB of evaluation records and logs; retention 30 days by default |
| support | best-effort email support during the demo, no SLA |
| cancellation | effective at period end; exports remain downloadable for 30 days |

Not implemented: accounts, checkout, subscription state, entitlement enforcement. They
need the hosting decision (item 5) and a payment-provider choice, and must stay inactive
until the owner approves activation.

## 7. Downloadable application — partly done

Done: wheel-based preview (`scripts/build_studio_bundle.py`), compatibility information in
Studio (Docker engine type, GPU runtime availability in the recipe catalog, actionable
errors for missing Docker, out-of-memory, disk space, digest mismatches).
Also done: preflight refusals before preparing or starting; `furnace studio-cleanup` (dry run
by default, refused while Studio runs) removes this workspace's containers and networks and,
optionally, the weights store and pinned images; `scripts/package_release.py` builds a
versioned candidate (`furnace-studio-<version>+<commit>.zip`) with `SHA256SUMS` and
`release.json` (commit, hashes, verified platforms read from the recorded runs) and refuses a
dirty tree. Procedure: [release-procedure.md](../operations/release-procedure.md).
New draft milestone: self-contained per-user Windows installer, terminal-free launcher,
first-run Docker check and a Studio-first download site. See
[Windows download operations](../operations/windows-download.md) and its linked evidence.
Not done: manual fresh Windows/macOS consumer-profile installation test, automatic
updates, publisher signing, and publication itself (an outward-facing step that needs owner
approval).
Verified operating systems for the managed model path: **Windows 11 with Docker Desktop
(WSL2 engine) only**. The Docker-level isolation tests also run on Ubuntu 24.04 in CI.

## 8. Website — combined candidate under review, not deployed

The public site remains the recorded demonstration. The combined review candidate
contains a simpler public website and local Studio journey, including the managed
local-model path. These are distinct interfaces; local work is not publicly deployed.
The older visitor-journeys branch remains preserved separately. Publication needs
owner approval and human comprehension testing; browser automation is not that evidence.

## 9. User testing and operational readiness — procedures written; people still needed

Written for the local application: [recovery runbook](../operations/recovery-runbook.md),
[privacy and retention](../operations/privacy-and-retention.md),
[support](../operations/support.md) and [release procedure](../operations/release-procedure.md).
They describe tested behaviour only and must be revised once a hosted service exists.
Still needed: the owner's own walkthrough, then an unfamiliar developer. Automated browser
tests and the validation script do not replace that.

## What is needed from the owner next

1. Walk through Studio's `/model` page with one of the two pinned models and note confusion.
2. Confirm or change the first demo model (recommendation: Qwen2.5 0.5B for reliability,
   with Granite 4.0 H 350M as the non-transformer example) and the hardware it runs on.
3. Decide hosting provider, spend limit and demo access (item 5), then accept or change the
   plan proposal (item 6).
