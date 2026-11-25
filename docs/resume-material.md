# Resume and LinkedIn draft

## Current document-product prototype — resume options

- Built Furnace (Python, FastAPI, Docker, llama.cpp), a local document-AI prototype
  with summarisation, Q&A and rewriting, while preserving an Advanced model workspace.
- Added per-answer privacy receipts bound to model identity and observed container
  isolation; tested that document text and answers stay out of application records,
  logs and exported kits, without claiming host-wide traffic proof.
- Built a self-contained, per-user Windows installer with bundled Python, automatic
  browser launch and clean shutdown; verified installation and uninstall retention in CI.

Evidence: [contract](https://github.com/dilipna/Furnace4LLM/blob/product/private-documents/docs/product/private-documents.md),
[actual installed CPU/GPU outcomes](https://github.com/dilipna/Furnace4LLM/blob/product/private-documents/docs/product/everyday-validation.md).
These are draft features, not a published release. Historical v2 runs completed 11 tasks
on CPU/GPU with 5/9 rule passes and 2 unscored. Corrected v3 re-scoring of those same outputs
is separate from new inference. The later 36-case comparison includes a Qwen3 CPU timeout
and retained failures; see the [full comparison](https://github.com/dilipna/Furnace4LLM/blob/product/private-documents/docs/product/model-comparison.md).
Do not claim semantic accuracy, professional suitability or customer adoption.
The pilot placeholder below remains blank.

## Earlier Studio bullets — alternative engineering material

- Built Furnace (Python, FastAPI, Docker, llama.cpp), a local platform
  that runs open-weight LLMs as isolated, monitored services with automated
  evaluations and crash recovery; directed AI coding agents (Codex, Claude Code)
  through pull requests and CI.
- Validated two model architectures end to end—Qwen2.5-0.5B (transformer) and
  Granite-4.0-H-350M (Mamba-2 hybrid)—on CPU and NVIDIA GPU, including injected
  crashes and restarts; 12/12 outputs matched across relaunches in recorded trials.
- Hardened model containers with non-root execution, read-only filesystems and
  an internal model network with no internet route; launch keys excluded from
  application records, logs and exports.
- Fixed reliability bugs with regression tests, including a shutdown race that
  overwrote finished results and a Windows TCP reset in the adapter host;
  700+ tests passing in CI.

## Future pilot bullet — placeholder, not a resume claim

[After the pilot case study: helped PARTICIPANT accomplish TASK on ENVIRONMENT;
diagnosed OBSERVED FAILURE, delivered FIX and verified OBSERVED OUTCOME. Link the
dated case study and distinguish assisted steps from independent actions.]

Do not fill this from a planned session or an automated browser check.

## Evidence behind the claims

1. [Architecture and operating model](interview-guide.md),
   [runtime implementation](../packages/furnace/src/furnace/runtime/) and
   [API implementation](../apps/api/) support the delivery and technology claims.
   Dilip confirmed directing Codex and Claude Code in his November 23 revision
   request. This is owner-attested tool attribution, not independent human review
   or evidence that the application itself provides an AI assistant.
   PR #14 merged as `963c48478fc8eda82ffb65006db8adaa8185cc29`.
   Omit the proposed “16 reviewed pull requests”: PR numbering is not a count of
   merged, independently reviewed changes. On November 22, the merged-PR listing
   contained 12 entries, including ancestor integration; no review-count claim is made.
2. [Real-model trial table](product/real-model-validation.md) links the raw records in
   [verification](product/verification/). The five model records report restart
   reproducibility of 12 compared and 12 identical outputs. These are historical runs
   on one Windows 11/Docker Desktop machine with an RTX 3050 Ti, not new runs of the
   current release. Output identity does not establish answer quality. Failed scores
   remain recorded. Granite is a hybrid, not universal non-transformer compatibility.
3. Container controls and key exclusion are documented in the
   [runtime implementation](../packages/furnace/src/furnace/runtime/) and
   [real-model records](product/verification/).
   Docker administrators can inspect container environment credentials: “keys never
   persisted” would be too broad. Keys are excluded from application records, logs
   and exports. Network restrictions do not isolate the service from its Docker host.
   The exact supported claim is that the internal model network has no internet
   route, not that every Furnace component has no internet access. Preparation
   downloads assets; a relay also joins the Docker bridge.
4. [Model lifecycle tests](../apps/api/tests/test_studio_model.py), specifically
   `test_shutdown_recovery_never_rewrites_a_batch_that_ended_while_it_waited`,
   cover the shutdown race. [Adapter tests](../packages/furnace/tests/test_adapter_contract.py),
   specifically `test_researcher_host_speaks_the_protocol_used_by_studio` and
   `test_researcher_host_reports_failed_load_and_rejects_invalid_requests`,
   check the expected HTTP errors instead of a reset. The
   [interview guide](interview-guide.md#three-verified-bug-stories) links both fixes and the
   original Windows observation in PR #11. Both fixes have regression coverage;
   the repository does not establish test-before-fix chronology for both, so the
   resume does not claim “regression-first.”
   [Hosted CI on PR #14 head `9056f93`](https://github.com/dilipna/Furnace4LLM/actions/runs/44978375483)
   reported 712 passed and 1 skipped; this supports “700+”, not a new model experiment.
   [Merged-main CI](https://github.com/dilipna/Furnace4LLM/actions/runs/45060489476)
   also passed on `963c484`.

No paying customers, production uptime, independent user adoption or measured
onboarding-time reduction is established. The assisted pilot is planned for
November 29, 2026; observations and outcomes remain blank until it happens.

## LinkedIn description — two sentences

I’m building Furnace, a local app for sensitive documents, with privacy checks you can
inspect alongside each answer. I built its Windows installer and model infrastructure,
tested CPU and NVIDIA GPU journeys, and am preparing a user pilot.
