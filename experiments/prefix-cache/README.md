# Prefix caching and prompt layout

An independent, synthetic serving experiment built on FurnaceBench. Compare the same
operations runbook and queries with caching enabled, caching disabled, request metadata
before the shared prefix, and the same metadata after it. The question is whether prompt
layout changes cache reuse and streamed latency on this hardware.

The model is **Qwen2.5-0.5B-Instruct**, selected to reuse the existing 4 GB laptop setup.
It is not the originally proposed Qwen3-4B experiment. No 4B-model result is implied.
See the frozen [protocol](protocol.md), including the premeasurement input correction.

## Reproduce

### Review saved measurements first (no GPU)

From the repository root, Python 3.12 with only its standard library is sufficient:

```text
python experiments/prefix-cache/review.py
python experiments/prefix-cache/review.py --html experiments/prefix-cache/review.html
```

The first command is read-only and returns nonzero if evidence is missing or inconsistent.
It recomputes TTFT percentiles and throughput from all 720 request records, checks paired
workloads and frozen source hashes, recalculates cache-token reuse from Prometheus
snapshots, checks image/cache toggles, and checks the JSON and three published Markdown
tables. This establishes internal consistency, not independent proof of provenance.
The second command writes a portable report with no external assets or JavaScript. Open
`review.html` in a browser; the run table retains all observed tails and the failed startup.
Opening the HTML shows a snapshot; rerun the command to verify the current tree.

The `evidence` GitHub Actions workflow needs no model, Docker, account secret or API key.
The normal Python CI job also collects the experiment's protocol and corruption tests.

### Rehearse the actual Forge regression test

```text
python experiments/prefix-cache/rehearse_guard.py
```

This runs the prefix-stability test shipped by Forge against saved A/B/C/D prompts from
all three repeats. It does not implement a new proxy for that test or run inference.
A and D pass; C fails as expected in every repeat. B also passes: its prompt layout is
stable even though the server has caching disabled. That is a deliberate negative
control showing why the structural test cannot replace configuration and latency checks.
The rehearsal exits 0 only when all expected outcomes occur; `guard-replay.json` records
the observed character counts, template hash and test process exit codes.

For your own rendered base/head snapshots with identical questions in the same order:

```text
python experiments/prefix-cache/rehearse_guard.py --base base.jsonl --head head.jsonl --json prefix-check.json
```

Each JSONL row must contain `messages`, an array of text `role`/`content` objects ending
in a user question. At least two distinct questions are required. The command uses the
existing Forge policy: retain at least `int(base_shared_chars * 0.9)` leading characters.
Exit 0 means the structural test passed, 1 means it failed, and 2 means invalid inputs or
a test-execution error. A baseline with only shared role labels is refused. Render the
snapshots with your application separately; this command never imports your application.
Characters are not model tokens, and a structural pass does not prove cache hits,
answer equivalence or acceptable latency. See the [rehearsal walkthrough](guard-demo.md).

### Rerun inference (GPU required)

Use the repository's Python 3.12 environment, a Docker daemon with NVIDIA GPU access,
the pinned vLLM image, and the pinned model snapshot already present in the Hugging Face
cache. The driver does not pull images or download missing model weights. Connect AC
power and keep the GPU free of other work. The local service is bound to loopback only.

From the repository root, in Bash (Linux or Git Bash on the tested Windows/Docker setup):

```bash
bash experiments/prefix-cache/run.sh my-campaign
```

`HF_HOME_HOST` can point to a pre-existing Hugging Face cache. The script creates only
experiment-owned temporary containers and a Docker compilation-cache volume named
`furnace-prefix-compile`. Existing services are not stopped. The compilation cache affects
startup, which is outside measurement; each condition still gets a fresh inference server
and KV cache. Port 8115 must be available. Full runs take time because there are 12 fresh
server launches and 720 sequential measured requests, plus warmups.

Equivalent separate steps, also usable from PowerShell:

```text
uv sync --frozen
uv run python experiments/prefix-cache/benchmark.py --campaign my-campaign
uv run python experiments/prefix-cache/verify.py --campaign my-campaign
uv run --with matplotlib==3.10.8 python experiments/prefix-cache/render.py --campaign my-campaign
```

The plotting environment is separate from the timed measurement environment. No model
or serving flag is changed to make a failed condition pass. One identical retry is allowed;
failed attempts are preserved. Rendering refuses to create a complete table from an
incomplete campaign. A new campaign name is required for a new full run.

## Evidence layout

- `protocol.md`: conditions, controls, analysis units, failure policy and limits.
- `runbook.txt`: synthetic source; the served tokenizer selects a 1450–1500-token prefix.
- `runs/<campaign>/manifest.json`: versions, hashes, order, hardware and every attempt.
- `runs/<campaign>/prefix.txt`: exact shared system prefix.
- Each attempt: raw warmup and measured requests, workload payloads, metrics snapshots,
  and a summary. Server usage supplies completion-token counts.
- `server.log`: local, sanitized, ignored by Git; renderer emits a small tracked
  `cache-log-excerpt.txt` so cache-stat observations remain inspectable.
- `results.md`, `results.json`, `ttft-comparison.png`: generated only from a completed
  campaign. `verification.json` records independent consistency checks on raw artifacts.

The main table uses measured-window cache-counter deltas. Server log percentages are
shown separately with their logging-window limitation. Missing log statistics are stated
explicitly. Warmups and failed attempts never supply published performance values.

## Scope

One small model, one laptop GPU, synthetic inputs, concurrency one, fixed 32-token outputs,
and three independent server runs per condition. This measures serving behavior; it does
not assess answer quality or establish production impact. The chart's min–max whiskers
describe observed run variation and are not confidence intervals.

Offline protocol checks:

```text
uv run pytest -q --confcutdir=experiments/prefix-cache experiments/prefix-cache
```

`--confcutdir` isolates these tests from the main application's database setup.

No command here commits or pushes. Publication remains a manual review step.
