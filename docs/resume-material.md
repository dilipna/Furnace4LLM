# Resume and LinkedIn draft

## Three resume bullets

- Built Furnace (Python, FastAPI, Docker, llama.cpp), an AI-assisted local platform
  that runs open-weight LLMs as isolated, monitored services with automated
  evaluations and crash recovery.
- Validated two model architectures end to end—Qwen2.5-0.5B (transformer) and
  Granite-4.0-H-350M (Mamba-2 hybrid)—on CPU and NVIDIA GPU, including injected
  crashes and restarts; 12/12 outputs matched across relaunches in recorded trials.
- Hardened model containers with non-root execution, read-only filesystems and
  network restrictions; kept launch keys out of application storage and fixed a
  shutdown race that overwrote finished results, backed by 700+ passing CI tests.

## Fourth bullet — pilot placeholder, not a resume claim

[After the pilot case study: helped PARTICIPANT accomplish TASK on ENVIRONMENT;
diagnosed OBSERVED FAILURE, delivered FIX and verified OBSERVED OUTCOME. Link the
dated case study and distinguish assisted steps from independent actions.]

Do not fill this from a planned session or an automated browser check.

## Evidence behind the claims

1. [Architecture and operating model](interview-guide.md),
   [runtime implementation](../packages/furnace/src/furnace/runtime/) and
   [API implementation](../apps/api/) support the delivery and technology claims.
   AI assistance is disclosed; it does not establish independent human review.
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
3. [Model lifecycle tests](../apps/api/tests/test_studio_model.py) cover the shutdown
   recovery race. Container controls and key exclusion are documented in the
   [runtime implementation](../packages/furnace/src/furnace/runtime/) and
   [real-model records](product/verification/).
   Docker administrators can inspect container environment credentials: “keys never
   persisted” would be too broad. Keys are excluded from application records, logs
   and exports. Network restrictions do not isolate the service from its Docker host.
   [Hosted CI on PR #14 head `9056f93`](https://github.com/dilipna/Furnace4LLM/actions/runs/44978375483)
   reported 712 passed and 1 skipped; this supports “700+”, not a new model experiment.
   [Merged-main CI](https://github.com/dilipna/Furnace4LLM/actions/runs/45060489476)
   also passed on `963c484`.

No paying customers, production uptime, independent user adoption or measured
onboarding-time reduction is established. The assisted pilot is planned for
November 29, 2026; observations and outcomes remain blank until it happens.

## LinkedIn description — two sentences

I built Furnace, a local app that helps researchers run open-weight models with
isolated serving, evaluations, logs and crash recovery. I’ve tested Qwen and Granite
on CPU and NVIDIA GPU, and I’m preparing a hands-on pilot with another developer.
