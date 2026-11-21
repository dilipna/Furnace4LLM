# Furnace-operated local model servers

Studio can now prepare and operate a model server itself instead of requiring one the
researcher already runs. This page is the operating contract: what Furnace does, what it
isolates, how failures and restarts behave, and how a new architecture plugs in.
Validation results for the two pinned models are in [real-model-validation.md](real-model-validation.md).

## The journey in Studio

Open **Connect a local model server** (`/model`) and pick a project.

Browsing recipe metadata does not require Docker. If the CLI/daemon is unavailable or
inspection times out, the catalog remains readable, reports Docker unavailable and uses
`null` for unconfirmed image presence. It creates no preparation job or model execution.
Preparing and starting still require working local Linux-container Docker and consent.

1. **Choose a reviewed recipe** and accelerator (CPU or NVIDIA), with container memory,
   CPU threads, context size, request timeout, tokens per request and an evaluation budget.
   Saving downloads nothing.
2. **Prepare** (explicit consent). Furnace pulls the pinned server image and relay image by
   digest and downloads the pinned weights. Progress is shown; preparation can be cancelled
   and resumes from the partial file next time.
3. **Load reference suite** (optional). Replaces the project's cases with the recipe's
   pinned suite (twelve rule-scored task checks).
4. **Start** (explicit consent). Furnace re-hashes the weights, starts the isolated server,
   waits until the server itself reports healthy, then connects the evaluation steps on the
   same page to it automatically.
5. **Try a request**, **Run endpoint cases**, inspect **attempt history** and
   **reproducibility**, and **Show health, metrics and logs**.
6. **Export kit**: `workspace-plan.json` carries `managed_server` (manifest, launch, status),
   `model_endpoint` (runs and history) and `operations`; `serving-manifest.json` is the full
   pinned manifest whose SHA-256 every run cites.
7. **Stop**. The containers and network are removed.

Command-line equivalent for a whole recorded journey:
`uv run python scripts/validate_managed_model.py --model <recipe> --accelerator cpu|nvidia --out <file>`.

## What is pinned (the durable version record)

`packages/furnace/src/furnace/runtime/catalog.py` holds reviewed recipes. A recipe pins:

| input | how it is pinned |
| --- | --- |
| server engine | llama.cpp release b12004 (commit `3c809f4`), container image by multi-arch index digest, separately for CPU and CUDA 12 |
| relay | `alpine/socat` 1.8.1.1 by digest |
| weights | Hugging Face repository at a 40-character revision, exact byte size and SHA-256 |
| launch | context size, threads, memory, CPU share, GPU layers, generated-token cap, parallel slots (1), `--offline` |
| reference suite | packaged JSONL whose SHA-256 is pinned; a changed file refuses to load under the old identity |

The canonical JSON of these values is the **serving manifest**; its SHA-256 identifies the
configuration. Restarting the same manifest keeps the same evaluation identity (the per-launch
port and launch ID are excluded), so runs before and after a restart are comparable.
Adding a model means adding a reviewed recipe and recording its validation; nothing is
discovered or downloaded from an unpinned source.

## Isolation and secrets

Per project, Furnace creates:

- an `--internal` Docker network (external routes restricted; this does not guarantee isolation from host bridge services);
- the **model container**, attached only to that network: user `10001:10001`, read-only root
  filesystem, 64 MiB `noexec` tmpfs, all capabilities dropped, `no-new-privileges`, memory
  limit with swap disabled, CPU share, 256-process limit, open-file limit, weights bind-mounted
  read-only, `--gpus all` only for the NVIDIA option;
- a **relay container** (socat) on that network and the default bridge, published only on
  `127.0.0.1` with a Docker-assigned port, read-only, no capabilities, 64 MiB.

Each launch generates a random API key. It is passed to the server through the Docker CLI's
environment (not the command line), required by the server for completions, metrics and the
model list. Studio keeps its copy in memory; Docker retains it in container configuration.
It is never written to the workspace database,
the operations log or exports. Studio discards its copy on stop; Docker's copy is
removed with the container. Anyone with access to the
Docker daemon can still read container environments; the daemon is trusted host
infrastructure, as for the existing fixture.

Docker's [internal-network documentation](https://docs.docker.com/reference/cli/docker/network/create/#network-internal-mode---internal)
allows communication with the gateway address and appropriately configured host
services. This implementation does not use isolated gateway mode. Docker also
[stores container environment variables in configuration](https://docs.docker.com/engine/cli/proxy/#configure-the-docker-client).
Treat the local Docker administrator and host services as trusted; this preview
is not a multi-tenant boundary for hostile model code.

Not covered: Furnace does not attest the code inside the pinned engine image beyond its
digest, does not sandbox the Docker daemon itself, and does not encrypt local workspace files.

## Readiness, health and monitoring

- **Readiness** is the server's own `/health` (503 while loading, 200 when ready, 500 when
  loading failed), polled while the container is checked for an exit. A start reports
  `starting` → `loading` → `ready` and records start and load seconds.
- **Failure detection**: every status read inspects the container. An exited container
  becomes `failed` with `server_out_of_memory` or `server_exited_<code>`, the connection is
  marked failed, the containers are removed and nothing restarts on its own.
- **Observation** (`/managed/observe`): container state and networks, CPU/memory/process
  counts from `docker stats`, host GPU memory, utilisation and temperature for NVIDIA launches, the server's Prometheus counters (prompt and generated tokens,
  seconds, requests processing), a bounded server log tail with the key redacted, and the
  project's recent operations.
- **Operations log** (`<workspace>/logs/operations.jsonl`): one JSON line per event —
  prepare, ready, stop, connect, each request with its request ID, duration, token counts and
  status, evaluation start/end, failures with their error category. It refuses fields named
  `input`, `output`, `prompt`, `messages`, `content`, `key`, `api_key` or `token`, rotates at
  1 MiB (five files) and drops entries older than the project's log-retention setting at startup.

## Limits and timeouts

| limit | value |
| --- | --- |
| container memory | 512–16384 MiB (default 2048), no swap |
| CPU share / threads | 0.5–16 / 1–16 (default 4 / 4) |
| context | 512–8192 tokens (default 4096) |
| server generation cap | `--n-predict` = max(recipe setting, tokens per request), ≤ 1024 |
| request timeout | 1–120 s (default 60), wall clock including a slow body |
| evaluation budget | 10–1800 s (default 600); unexecuted cases stay `not_run` |
| server read/write timeout | 600 s |
| load timeout | 180 s for llama.cpp recipes |
| response size | 256 KiB; completion text ≤ 16 000 characters |

## Failure, retry and recovery semantics

| event | result |
| --- | --- |
| download interrupted or cancelled | partial file kept privately; next prepare resumes with an HTTP range; never served |
| downloaded bytes do not match | discarded (`download_digest_mismatch`) |
| stored weights altered later | quarantined at the next start (`artifact_digest_mismatch`); start refused |
| server runs out of memory or exits | `failed` with the reason; running batch stops with `error` for the case in flight; no hidden retry |
| request timeout | `endpoint_timeout`; connection marked failed; reconnect or restart explicitly |
| Stop | requests stop first, then containers and network are removed |
| Studio closed normally | managed servers are stopped with the application |
| Studio crashes | Docker keeps the containers running; on the next start Studio removes every container and network labelled for the workspace and marks the launch `interrupted` |
| retry | always explicit; a retry re-executes every case with new request IDs and keeps the failed attempt in history |

## Evaluations and references

Each case may carry a scoring rule: `exact`, `normalized` (case, width, whitespace and
surrounding punctuation ignored), `contains` (all values), `regex` (full match),
`numeric` (the last number in the answer that was not copied from the question, with
tolerance; all numbers if every one was copied), `choice` (exactly one option present as a
whole word) or `json_fields` (first JSON object, field values). Runs record the scorer
version (`furnace-rules-v2`); the numeric rule changed from plain "last number" after it
marked a correct Granite answer ("There are 180 minutes in 3 hours.") as wrong. Results are
`exact_pass`/`exact_fail`, `check_pass`/`check_fail`, `unscored`, `incomplete` (token limit
reached, never a pass) or `error`, each with a short reason code; outputs are stored as
SHA-256 hashes, not text.

Every run records the configuration identity, the suite digest, sampling (temperature 0,
tokens), the serving manifest digest, model, engine, accelerator, image, weights digest and
launch ID. **Reproducibility** compares output hashes with the previous completed run of the
same configuration, including runs from an earlier launch.

Rule checks are not human or semantic quality judgements. A small model failing a task is a
result, not an infrastructure error.

## Adapter contract for other architectures

`packages/furnace/src/furnace/runtime/adapter.py` defines what an adapter supplies; Furnace
supplies everything around it (verified artifacts, container, network policy, key, readiness,
logs, metrics, stop and recovery). Every adapter's server speaks protocol `furnace-chat-v1`
on container port 8080:

- `GET /health` → 200 `{"status": "ok"}` when loaded, 503 while loading, 500 if loading failed
- `GET /v1/models` → `{"data": [{"id": <model id>}]}`
- `POST /v1/chat/completions` → one text message, `stream: false`, `temperature: 0`,
  `max_tokens`; `Authorization: Bearer <key>` required when a key is supplied; one choice with
  `message.content` and `finish_reason` `stop` or `length`
- `GET /metrics` → optional Prometheus text

Two adapters ship:

- **`LlamaCppAdapter`** — GGUF weights served by the pinned llama.cpp image. Covers the
  transformer and state-space/hybrid architectures llama.cpp implements.
- **`PythonAdapter`** — for architectures no engine supports. The researcher provides an
  image pinned by digest containing their dependencies, a code directory (mounted read-only)
  and `module:factory` returning an object with:

  ```python
  load(weights_dir: str | None) -> None
  generate(messages: list[dict], max_tokens: int, temperature: float) -> tuple[str, str]
  reset() -> None   # optional; called before every request to clear recurrent state
  ```

  Furnace mounts its standard-library host `pyserve.py`, which implements the protocol,
  serves one request at a time, enforces the key, reports load failures through `/health`,
  and never returns adapter error text to callers.

In Studio, choose **Your own Python adapter (advanced)** in the model list and supply the
image (`name@sha256:…`, or `sha256:…` for a locally built image that is already present), the
absolute code folder, `module:factory`, the model ID to advertise and, optionally, a weights
folder. The code folder is digested by content into the serving manifest, so editing the code
changes the configuration identity and older runs no longer count as current; symbolic links
in it are refused. The weights folder is recorded by file names and sizes only, and the
evidence says so (`weights_verified_before_launch: false`). Preparation only confirms the
image is present (registry images are pulled by digest); there are no pinned weights to
download. The reference suite can be loaded for any adapter.

The same isolation applies as for recipes. The code runs as the researcher wrote it, inside
the container: Furnace bounds what it can reach (no network route, read-only mounts, resource
limits), but does not review the code. Tested end to end through Studio on real Docker with a
deterministic test adapter (`apps/api/tests/test_studio_adapter_docker.py`); no researcher's
own model has been validated yet.

## Preflight checks

Before preparing or starting, Studio checks the local Docker engine and refuses with an
actionable reason instead of failing later:

| code | meaning and fix |
| --- | --- |
| `docker_unavailable` | Docker is not reachable: start Docker Desktop |
| `linux_containers_required` | switch Docker Desktop to Linux containers |
| `gpu_runtime_unavailable` | NVIDIA chosen but Docker offers no GPU runtime: choose CPU or enable GPU support (WSL2, current driver) |
| `memory_exceeds_docker_limit` | the memory limit exceeds what Docker can provide (keeping 512 MiB headroom): lower it or raise Docker's memory |
| `cpus_exceed_docker_limit` | more CPUs than Docker has: lower the CPU setting |
| `insufficient_disk_space` | not enough free space for the weights (checked by the download) |

## Cleanup and uninstall

`furnace studio-cleanup` removes what Furnace-operated servers left on the machine, and
nothing else. It refuses while Studio owns the workspace, and is a dry run unless `--yes`
is given:

```sh
uv run furnace studio-cleanup --workspace ~/.furnace/studio                 # list
uv run furnace studio-cleanup --workspace ~/.furnace/studio --yes           # remove containers and networks
uv run furnace studio-cleanup --workspace ~/.furnace/studio --artifacts ~/.furnace/studio/artifacts --images --yes
```

It removes only containers and networks labelled for that workspace; with `--artifacts`
only the store's `blobs`, `partial` and `quarantine` folders; with `--images` only the pinned
engine and relay images (an image still used by another container is left in place). Model
folders, project files, exports and unrelated Docker resources are never touched.
To uninstall Studio completely, run the cleanup with `--artifacts --images --yes`, then delete
the extracted bundle and the dedicated workspace folder.
