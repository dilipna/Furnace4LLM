# Furnace

[![ci](https://github.com/dilipna/Furnace4LLM/actions/workflows/ci.yml/badge.svg)](https://github.com/dilipna/Furnace4LLM/actions/workflows/ci.yml)

**Make your LLM faster without breaking it.**

Furnace is an inference-reliability retrofit for LLM applications that already exist.

- **Scan** reconstructs an app from its repository into a *behavior-to-code reliability graph* and
  a Blueprint of evidence-backed findings (every claim cites a file and line, with a confidence).
- **Forge** opens a draft pull request that installs only what the Blueprint justified, after
  validating it in a sandbox.
- **Guard** runs only the evals and serving benchmarks a pull request can affect, reports a GitHub
  check run, and on a prompt-cache regression writes the failing test first, tries repair
  strategies in order, validates each in a sandbox and against a perf gate, and opens a draft PR
  with the one that passed. A human always merges.

Every number in this repository comes from a documented command; negative results and
corrections are reported. See **[FurnaceBench](docs/furnacebench.md)**, the reports in
`bench/results/<date>/`, and the dated `CORRECTIONS.md` shown on the `/bench` page.

## Measured so far (laptop RTX 3050 Ti, vLLM, Qwen2.5-0.5B)

| question | result | source |
|---|---|---|
| Does Scan find LLM call sites in apps it has never seen? | held-out set 3 (Gemini, Mistral, Replicate, Bedrock, Cohere apps, labeled before any scan): **8/9** at precision 1.00; held-out set 1: 8/8 | `bench/results/2026-10-09/RQ1_NOTES.md` |
| How large is a prompt-cache regression? | R1 (request id at the top of the system prompt): p95 TTFT **+905% to +1,004%**, prefix-cache hit 98% -> 0% | `bench/results/2026-10-09-gate-warmup-v2/rq5.md` |
| Can Furnace repair it without making things worse? | **3/3 verified**, -2.0% to +8.5% vs main (inside the 9.7% measured noise), full-suite audits clean; its first candidate was **blocked by its own gate** (+44% to +50%) | same |
| Is the perf gate trustworthy? | A/A (main vs itself): within 9.7% after a warmup fix; before it, up to 60% and biased, so an earlier RQ5 claim was withdrawn | `bench/results/2026-10-09/gate_noise.md`, `bench/results/2026-10-06/CORRECTIONS.md` |
| Does Guard save time? | 13 PRs: ran 46% of checks, caught 3/3 full-suite failures, same conclusion 13/13 | `bench/results/2026-10-06/rq3.md` |
| What does prefix caching buy on the real workload? | caching off raised p95 TTFT in all 15 cells, same sign in every paired repeat: +193% to +433% at max-num-seqs 32 (median per cell), +96% to +433% across all configs | `bench/results/2026-10-06/rq4/rq4.md` |
| Triton RMSNorm kernel | correct 36/36; at parity with `torch.compile` (both ~9.8x eager, 99% of copy bandwidth) | `kernel_lab/results/2026-10-09/` |

## What works today

| area | status |
|---|---|
| Scan of public GitHub repos / ZIPs: Python code (OpenAI, Anthropic, Groq, Ollama, LiteLLM, Cohere, Mistral, Google, Hugging Face, Bedrock, Replicate, llama.cpp, LangChain), routes, Streamlit/CLI workflows, Blueprint, contradictions, graph | working; other languages are reported as not analyzed (their configs and docs still are) |
| Live views: lab telemetry (vLLM /metrics + NVML), "Run it now" benchmark, Guard run streamed check by check, graph path trace, scan terminal | working locally; hosted deploys show the recorded runs, labeled |
| `furnace-bench` load generator (TTFT/TPOT/goodput, CIs, telemetry, mock-validated) | working |
| Inference Lab: prefix-cache and scheduler sweep on the real F1 workload | working (RQ4) |
| Guard: graph-targeted checks, warmed-up perf gate, local runs and GitHub check runs | working locally; the GitHub path is tested against a mock API, first live run needs the [App](docs/github-app.md) |
| Repair of prompt-prefix regressions: two rule strategies tried in order | working (RQ5); LLM-patch strategy not built |
| Forge change set (evals, prompt extraction, benchmarks, CI gate), sandbox-validated | working on F1; draft-PR path awaits the App |
| Webhook: verified `pull_request` events enqueue Guard runner jobs | built and tested; not run against a live App yet |
| Deterministic evals; human labeling queue | working; LLM-judge calibration needs a BYOK key and labels |
| Hosted control plane (Vercel + Render + Supabase) | deploy files ready ([guide](docs/deploy.md)) |
| Not built: auth/orgs, BYOK storage, TypeScript/JS extraction, LLM synthesis, Stripe | see [security](docs/security.md) and FurnaceBench "Not run" |

## Layout

| path | what |
|---|---|
| `apps/api` | FastAPI: scans, SSE logs, Blueprint, graph, live lab telemetry and runs, Guard runs, FurnaceBench results, labeling |
| `apps/web` | Next.js UI: landing, Blueprint, graph, Inference Lab, Guard, Evaluations, FurnaceBench, pricing |
| `packages/inference` | `furnace-bench`, standalone (no dependency on the rest of Furnace) |
| `packages/furnace` | extraction, reconstruction, Blueprint, evals, Forge, Guard, repair, GitHub, sandbox, jobs, CLI |
| `fixtures/` | F1 (`support-rag-py`, RAG + approval-gated tool on vLLM) and its scripted PR scenarios |
| `bench/` | FurnaceBench drivers, ground truth, results |
| `kernel_lab/` | Triton RMSNorm |
| `scripts/` | `demo_up.ps1`, `preflight.py`, `rehearse.py`, `demo_shots.py`, `demo_repo.py` |
| `docs/` | [architecture](docs/architecture.md), [security](docs/security.md), [FurnaceBench](docs/furnacebench.md), [GitHub App](docs/github-app.md), [deploy](docs/deploy.md), [demo](docs/demo.md) |

## Quickstart (development)

```bash
uv sync
docker compose up -d postgres            # Postgres 17 on :5433
uv run poe migrate
uv run poe api                           # API on http://localhost:8010
uv run poe worker                        # runs scans (without it, scans stay "queued")
uv run poe runner                        # runs Guard jobs (needs Docker for the sandbox)
cd apps/web && pnpm install && pnpm dev --port 3100   # web; /api/* is proxied to :8010

# GPU lab (optional): vLLM serving Qwen2.5-0.5B-Instruct as "lab" on :8100
HF_HOME_HOST=$HOME/.cache/huggingface docker compose --profile gpu up -d vllm
```

On Windows, `uv run poe demo-up` does all of the above (with a production web build) and ends
with `scripts/preflight.py`, which checks power mode, every service, the GPU clock under load, a
live stream through the web proxy and the GitHub App. `uv run poe demo-down` stops it.

Checks: `uv run poe check` (ruff, format, import-linter, pyright, pytest; the sandbox tests need
Docker). Web: `pnpm lint && pnpm exec tsc --noEmit` in `apps/web`. CI runs both on every push.

## Runner commands

```bash
uv run furnace gh-check                                  # verify the GitHub App
uv run furnace gh-forge OWNER/REPO [--open-pr]           # Forge
uv run furnace gh-guard OWNER/REPO PR --suite FILE.py    # Guard check run
uv run furnace gh-repair OWNER/REPO PR --suite FILE.py [--open-pr]
uv run poe bench-gpu                                     # FurnaceBench GPU campaign (RQ4, RQ3, RQ5, report)
uv run python bench/gate_noise.py                        # perf-gate A/A noise calibration
uv run poe kernel-correctness && uv run poe kernel-bench # Kernel Lab
uv run python scripts/rehearse.py [--video DIR]          # rehearse the demo path in a browser
```

GPU numbers depend on the laptop's power state and on the clock the driver picks for this light
serving load (780 MHz on Oct 6-9, ~1,960 MHz on Oct 11 after a reboot; never throttled), so every
result records its clock and comparisons are made only inside a set that shares one
(`bench/results/2026-10-11-live-clock/`). FurnaceBench GPU drivers refuse to run on battery.
