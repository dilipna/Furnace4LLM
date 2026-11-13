# Researcher infrastructure platform: owner direction

This direction supersedes the earlier pre-merge-check positioning for new product work.
The existing Guard/benchmark code remains useful infrastructure, not the whole product.

Customer: researchers developing models, including architectures beyond transformers.
They focus on model training/testing. Furnace supplies the surrounding operational system.
Journey: download Furnace from the website; inspect a model project locally; receive a
free starter kit showing useful additions and missing pieces; optionally subscribe for
$20 to infrastructure Furnace operates, including serving, harness, security, evaluations,
logs and related operational needs. Initial demo capacity: one or two models, not fleet scale.

Open owner decisions: demo model repositories/checkpoints; subscription billing interval;
who supplies and pays for compute. Do not silently set these or advertise checkout,
unlimited compute, universal architecture support or production readiness.

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

1. Free local inspection and kit export, with unknowns visible (this branch).
2. One selected real research model: reviewed loader/adapter, real inference and explicit
   supported device/input/output contract. A paper alone is not executable compatibility.
3. One complete operated demo: server lifecycle/readiness, authenticated inference,
   structured redacted logs, resource limits, task-specific evaluation results, controlled
   failure/recovery and clean stop. Add a second model only after the first proves the path.
4. Downloadable application and setup experience connected to that working lifecycle,
   with a truthful free/paid boundary. Packaging target follows the selected supported runtime.
5. Subscription and managed infrastructure after the owner confirms billing interval,
   compute ownership/funding and the actual offer. No charges, provisioning or publication
   are authorized by the local implementation alone.

Existing model-endpoint benchmarking can be reused where the new model exposes a
compatible interface. Architecture support must be proven per adapter; do not force a
new architecture into a transformer-specific runtime. Existing application scanning,
Guard and repair remain available but are not the researcher's onboarding entry point.
