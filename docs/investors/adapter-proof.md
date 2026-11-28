# New-architecture proof — pending final freeze

## Actual result

**Not started.** The final dual-journey candidate is not yet frozen/accepted. The owner
scheduled this experiment after freeze, timeboxed to one working day. No model download,
image build or new inference happened for this investor task. Prerequisite hold, not
an observed compatibility failure. Existing deterministic PythonAdapter tests and
Granite through llama.cpp do not qualify. No timing or result is filled in below.

## Candidate selected for investigation

[MDLM OWT author card](https://huggingface.co/kuleshov-group/mdlm-owt/raw/main/README.md):
masked diffusion, approximately 130 million non-embedding parameters, context 1024.
Author card declares Apache-2.0; [author code licence](https://raw.githubusercontent.com/kuleshov-group/mdlm/master/LICENSE)
also does. Reconfirm exact model/dependency licences and pin upstream revisions before
execution. Non-embedding count is not total size. MDLM uses a Transformer denoiser;
call it a different generation architecture, not a non-Transformer or chat-tuned model.

The [config](https://huggingface.co/kuleshov-group/mdlm-owt/raw/main/config.json) identifies
`mdlm` with custom code. The [pinned engine inventory](engine-inventory.json) has no
MDLM entry. This is selection evidence, not an executed refusal or a statement about
all engines. Audit the final frozen engine again first. If it serves MDLM, select
another permissive unsupported model rather than manufacture a boundary.

## Unchanged-platform protocol

Use a disposable folder outside frozen installation/checkout. Read PythonAdapter in
the exact frozen source and [boundary snapshot](evidence/boundary.md). Researcher supplies:

- Adapter module using existing factory/load/predict response contract. Native masked
  diffusion sampling, not an autoregressive substitute, canned answer or monkeypatch.
- Immutable digest/local-content-ID dependency image, locked versions, pinned base.
  Review code before opting into remote loading. Cache model/code/tokenizer for offline
  runtime and retain hashes. Image build is preparation, outside inference isolation.
- Existing manifest with pinned code/weights/image, bounded CPU/RAM/output/context.
  CPU first; optional GPU if time permits. No global Docker settings or paid service.

Archive 12 bounded prefix/continuation or masked-restoration tasks before execution,
with seeds, steps and rules. Not chat-tuned: keep native task quality separate from
completed execution, repeat equality and restart equality. Preserve failed/unscored tasks.

Start monotonic time when taking the received model folder. Include adapter writing,
image build and investigation through the first complete evaluated 12-case service run.
Record initial prerequisites/cache state and separate downloads/setup intervals; no
warm-start latency disguised as end-to-end minutes. If folder pre-staged, say so and
retain its earlier preparation interval. Also record total work time and stopping time.

Use unchanged Studio: register → preflight → explicit prepare/start → predict →
evaluate → repeat → crash during evaluation → verify interruption/error and no hidden
retry → explicit restart → identical suite → compare outputs → export → stop/cleanup.
Retain requests/results, logs without secrets, hashes, Docker observations and commands.
If Studio reopen is not exercised, say so.

**Stop if Furnace code needs changing.** Record exact command/input/error, source,
expected contract and minimal proposed fix for after December 4. Distinguish dependency
failure from platform failure. No patch to candidate, no timebox extension, no success
claim from a partial first response. A blocked integration is useful evidence.

## Results — actual observations blank

| Field | Observation |
| --- | --- |
| Frozen source/hash and separate experiment folder | |
| Model/code/tokenizer revisions/licences and dependency lock/base/image hashes | |
| Exact pinned engine audit | |
| Initial cache and download/build preparation intervals | |
| Clock start/first complete evaluation/elapsed minutes; total work time | |
| Completed predictions / planned 12; native task quality | |
| Repeat equality; crash actual queue/result states | |
| Restart equality; changed and wrong answers retained | |
| Export/log/network observations and cleanup | |
| Blocking error/stopping time/post-release fix if needed | |
