# Supporting research models: execution research and application decisions

Research date: 2026-11-13. Owner instruction: build the application first, then test
selected models; $20/month; both Furnace-provided and customer-provided compute;
one or two demo projects until funding. No cloud spend, billing activation or deployment.

## What “supported” must mean

A paper, architecture label, configuration file or checkpoint is not an executable
support contract. Record the exact code revision, checkpoint revision/license, tokenizer
or preprocessing, Python/framework/CUDA versions, device/memory, custom kernels,
input/output signature, state behavior and an executable author reference example.
Then prove loading, valid inference, invalid-input rejection, bounded failure, restart,
state isolation and representative task evaluations. Only that pinned combination can
be called validated. This is an engineering inference from the sources below, not a
claim that a model has been tested in Furnace.

## Evidence and implications

1. **State-space models.** The [Mamba implementation](https://github.com/state-spaces/mamba)
   exposes distinct core and CUDA-extension installation paths. Its native implementation
   and specialized kernels make dependency/device discovery part of onboarding. Do not
   assume installing a Python package establishes a working fast kernel. Review/pin an
   actual release and its prerequisites before the model test; no Mamba model was run here.
2. **Recurrent inference.** The [RWKV paper](https://arxiv.org/abs/2305.13048) describes
   parallelizable training and recurrent inference. A serving adapter therefore needs
   explicit request/session state ownership. State leakage between users, reset behavior
   and interleaved sessions must be acceptance tests, not incidental server details.
3. **Multiple execution modes.** [RetNet](https://arxiv.org/abs/2307.08621) describes
   parallel, recurrent and chunkwise recurrent computation. Architecture name alone does
   not select one execution path. Capture mode, context/state limits and reference outputs.
4. **Other recurrent families.** The [official xLSTM repository](https://github.com/NX-AI/xlstm)
   is another candidate family for later compatibility review. No checkpoint, implementation
   version, hardware requirement or runtime support has been validated in Furnace.
5. **Engine-specific compatibility.** [vLLM’s supported-model list](https://docs.vllm.ai/en/stable/models/supported_models/)
   lists specific architectures, including Mamba-related entries and per-model notes.
   Conclusion: vLLM can be useful for an explicitly supported revision, but cannot be a
   mandatory universal engine for arbitrary future research code. Registry support is
   upstream evidence, not a Furnace end-to-end compatibility result.
6. **Custom code is code execution.** [Hugging Face loading documentation](https://huggingface.co/docs/transformers/main/models)
   documents custom code and revision pinning. [PyTorch’s security policy](https://github.com/pytorch/pytorch/blob/main/SECURITY.md)
   treats untrusted models as a code-execution concern. Never automatically enable remote
   code, import a repository or deserialize arbitrary checkpoints during the free inspection.
   Any later execution needs a reviewed adapter, isolated environment and explicit action.
7. **Portable contracts.** [MLflow’s PythonModel guide](https://mlflow.org/docs/latest/ml/model/python_model/)
   separates custom prediction logic and model loading; its [signature documentation](https://mlflow.org/docs/latest/model/signatures/)
   makes inputs/outputs explicit. Adopt this separation in Furnace’s adapter boundary.
   MLflow is a comparison/reference, not a new application dependency or claimed integration.
8. **Operational health.** [Ray Serve fault-tolerance documentation](https://docs.ray.io/en/latest/serve/production-guide/fault-tolerance.html)
   distinguishes application health checks and failed replica recovery. Furnace must
   distinguish the local UI being reachable from model readiness, and readiness from a
   successful quality evaluation. Ray/Kubernetes are not needed for this two-project demo.

The architectural deductions are Furnace design decisions. They do not reproduce paper
benchmarks or establish that a proposed architecture beats transformers generally.

## Adapter paths to implement and validate after the application

| Path | Appropriate case | Required proof | Current Furnace status |
| --- | --- | --- | --- |
| Reviewed native adapter | Author provides custom Python/framework model implementation | Pin code/deps/checkpoint; reference inference; state/reset contract; bounded isolated execution | Contract capture only; execution not connected |
| Reviewed framework adapter | Compatible Transformers/custom-model API | Pin revisions; explicitly review custom code; tokenizer/input/output and device checks | No compatibility claim yet |
| Supported engine adapter | Exact model/revision supported by vLLM or another engine | Engine/model match, launch flags, readiness, inference, cancellation and telemetry | Prior endpoint benchmarks exist; no new research-model validation |
| Existing endpoint connector | Researcher already runs a server | Explicit request/response schema, auth, timeout, errors and task evaluation | Future connector; no arbitrary URL calls in Studio |

Support is a versioned registry entry: proposed → adapter implemented → acceptance passed.
Keep “unsupported”, “needs adapter”, “not tested” and “failed validation” distinguishable.
A family is not automatically supported because one member passed. No automatic model
conversion is required for the first application build. Preserve author checkpoints.

## Application-first implementation

Studio is a local loopback application using the existing FastAPI dependency, packaged
with HTML/CSS/JS assets and workspace wheels. It stores two project records in SQLite,
exports free kits, captures model contracts and both compute ownership choices, prepares
evaluation cases and records actual workspace events. It has session-token authentication,
origin/host restrictions and bounded forms. It makes no model-serving or billing calls.

The control application does not execute model code. The deterministic fixture already uses a separate worker. A future research-model worker must be a
separate isolated process/container with no control-plane secrets or Docker socket,
read-only model input where feasible, explicit network and resource policies, a timeout,
structured results and lifecycle control. Dependency installation is a separate trust
boundary. Do not run unknown author loading code in the Studio web process.

For the demo, a Python/uv wheel bundle is sufficient to review the full workspace journey.
A signed native installer and public website download need their own release verification.
The current ZIP requires Python 3.12/uv and installs pinned dependencies; it is not a
self-contained binary. No new serving framework, cloud account or billing service is added.

## Operational acceptance when a model is connected

- Author-reference inference and invalid-input behavior match the declared signature.
- Independent sessions do not share recurrent state; restart/reset behavior is defined.
- Start → loading → ready reflects actual worker state; crash/OOM/timeout report failure.
- Repeated start/stop and application restart leave no orphan worker or stale “ready”.
- Health endpoint distinguishes app, worker and model; circuit breaking/queue bounds apply.
- No auth bypass, raw secret logging, unexpected network access or source/checkpoint writes.
- Evaluation cases actually execute; missing results remain not_run/inconclusive, never pass.
- Logs contain request IDs, durations, error categories and bounded resource metrics;
  prompt/output capture is explicit, redacted where possible and governed by retention.
- Both compute modes share the same adapter protocol. Credentials/provisioning remain
  disabled in the demo; $20/month is the offer, not an unlimited-compute guarantee.
- Stop/uninstall and data removal preserve unrelated models and shared resources.

## Validation still pending

No research checkpoint was downloaded or executed. No new GPU evidence, customer
onboarding, billing event, remote provisioning or human usability result exists.
The earlier workspace-only milestone could not connect browser automation; subsequent
Studio browser/keyboard/responsive checks and installed-bundle tests are recorded in the
verification documents. They are automated observations, not human comprehension evidence.
Studio /guide provides the exact bounded real-endpoint CLI procedure and its missing
prerequisite; no real-model adapter is connected to Studio. Paper/vendor claims stay separate from these
application checks.
