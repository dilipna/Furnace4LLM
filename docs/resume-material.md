# Resume and LinkedIn draft

These describe implemented engineering, not a commercial service. PR #14 and its
dependent documentation/polish must retain their review status until merged. Do not
describe the planned pilot as an existing customer deployment.

## Three resume bullets

- Built Furnace, a local model-operations platform for pinned Qwen and Granite recipes,
  combining isolated Docker serving, rule-based evaluations, operational logs and
  configuration-bound evidence exports.
- Implemented explicit crash recovery and attempt history; validated a Qwen CPU workflow
  through 33 operational checks covering inference, restart, orphan cleanup, export and
  exclusion of per-launch keys from persisted records.
- Added researcher-adapter contracts, resource preflight and release-integrity checks
  that reject stale bundles and changed wheel bytes while preserving failed outcomes.

## Evidence and scope for each bullet

1. [Model trial table](product/real-model-validation.md) and its linked raw records establish
   the two named recipe examples. Granite is a Mamba-2/attention hybrid, not evidence of
   universal non-transformer compatibility. Real-model trials used one Windows/Docker
   machine; they do not establish macOS or Linux-host model support.
2. The 33 check outcomes are in
   [the Qwen CPU record](release/integration-verification/real-model-qwen-cpu-584e1b9.json).
   This historical run is tied to source `584e1b9`, not every later checkout. It scored
   11/12 rule cases; the failed case remains. Operational success is not semantic quality.
3. [Adapter tests](../packages/furnace/tests/test_adapter_contract.py),
   [preflight tests](../apps/api/tests/test_studio_managed.py) and
   [release tests](../packages/furnace/tests/test_release_package.py) support the engineering
   claims. PR #14 remains unmerged at preparation of this draft. The researcher adapter
   is exercised with an authored test adapter, not an independent learned model.

No measured onboarding-time reduction, paying users, production uptime, deployment
adoption or return usage is established. Add a pilot result only after writing its
dated case study and linking the actual evidence. Keep quantitative claims source-bound.

## LinkedIn description — two sentences

I’m building Furnace, an AI-assisted local platform that turns supported research models
into isolated services with evaluations, logs and crash recovery. The current focus is an
assisted user pilot, backed by source-bound Qwen and Granite trials and explicit limits
around model quality, hardware coverage and hosted deployment.
