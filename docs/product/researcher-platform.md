# Researcher infrastructure platform: owner direction

This direction supersedes the earlier pre-merge-check positioning for new product work.
The existing Guard/benchmark code remains useful infrastructure, not the whole product.

Customer: researchers developing models, including architectures beyond transformers.
They focus on model training/testing. Furnace supplies the surrounding operational system.
Journey: download Furnace from the website; inspect a model project locally; receive a
free starter kit showing useful additions and missing pieces; optionally subscribe for
$20/month to infrastructure Furnace operates, including serving, harness, security, evaluations,
logs and related operational needs. Initial demo capacity: one or two models, not fleet scale.

Owner clarification (2026-11-13): build the application before choosing/testing a model;
research supported model families thoroughly. The subscription is $20/month. Both
Furnace-provided and customer-provided compute are in scope. Demo operation precedes
funding, so paid provisioning and billing remain inactive. Model validation follows
application development; do not block the workspace on selecting a checkpoint.

First local implementation: free model-project inventory and starter-kit export.
No repository imports, checkpoint deserialization, inference, network, billing or provisioning.
File presence is evidence of a file, never verification that a capability works.
A custom architecture needs a reviewed model adapter and executable acceptance tests;
OpenAI-compatible serving and vLLM are optional integrations, not universal prerequisites.

Acceptance: local command inventories bounded regular files without opening .env files or
weights, retains only selected configuration metadata, reports unknowns, emits a useful kit without altering the model project, refuses
output overwrite, and has failure/security tests. This is a foundation, not the complete
downloadable application or paid managed service. Subsequent work needs the selected
model's real loading/inference contract, then one complete managed-demo lifecycle:
start, readiness, inference, authenticated access, logs, evaluations, restart and stop.

## Delivery order tied to this product

1. Free local inspection and kit export (implemented).
2. Local application: model projects, assessment, kit download, model contract,
   infrastructure preferences, evaluation cases, activity and removal (implemented locally).
3. Package a downloadable local preview (implemented). Exercise isolated execution,
   lifecycle, failures, evaluation evidence and recovery with a clearly labeled framework
   fixture before connecting a real model (current local milestone).
4. Select one model from the researched support paths; implement its isolated adapter
   and validate the complete lifecycle. Add the second model after that path works.
5. Review public website download, native installation and managed-service release.
   Billing and provisioning activation require a concrete, separately reviewed action.

See [model support research](model-support-research.md) for primary sources, compatibility
boundaries, adapter paths and acceptance tests. Existing Guard and benchmarks are reusable
components, not the researcher's product entry point. Runtime compatibility is not inferred
from file names, successful UI actions or passing framework tests.
