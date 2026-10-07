# Furnace

**Make your LLM faster without breaking it.**

Furnace is an inference-reliability retrofit for LLM applications that already exist.

- **Scan** reconstructs an app from its repository into a *behavior-to-code reliability graph* and
  a Blueprint of evidence-backed findings (every claim cites a file and line, with a confidence).
- **Forge** opens a draft pull request that installs only what the Blueprint justified, after
  validating it in a sandbox.
- **Guard** runs only the evals and serving benchmarks a pull request can affect, reports a GitHub
  check run, and on a prompt-cache regression writes the failing test first, repairs, validates and
  opens a draft PR. A human always merges.

Every number in this repository comes from a documented command; negative results are reported.
See **[FurnaceBench](docs/furnacebench.md)** and the latest report in `bench/results/<date>/REPORT.md`.

## What works today

| area | status |
|---|---|
| Scan of public GitHub repos / ZIPs (Python), Blueprint, contradictions, graph | working; held-out accuracy and its limits in RQ1 |
| `furnace-bench` load generator (TTFT/TPOT/goodput, CIs, telemetry, mock-validated) | working |
| Inference Lab: prefix-cache and scheduler sweep on the real F1 workload (laptop vLLM) | working (RQ4) |
| Deterministic evals; human labeling queue | working; judge calibration needs a BYOK key + labels |
| Guard: graph-targeted checks, perf gate (RQ3); GitHub check runs via the runner CLI | checks working; GitHub path tested against a mock API, first live run needs the [App](docs/github-app.md) |
| Repair of prompt-prefix regressions (rule strategy) | working (RQ5); draft-PR path awaits the App; LLM-patch strategy not built |
| Forge change set (evals, prompt extraction, benchmarks, CI gate), sandbox-validated | working on F1; draft-PR path awaits the App |
| Kernel Lab: Triton RMSNorm | code ready (`kernel_lab/`) |
| Hosted control plane (Vercel + Render + Supabase) | deploy files ready ([guide](docs/deploy.md)) |
| Not built: auth/orgs, BYOK storage, TypeScript extraction, LLM synthesis, webhook automation, Stripe | see [security](docs/security.md) and FurnaceBench "Not run" |

## Layout

| path | what |
|---|---|
| `apps/api` | FastAPI: scans, SSE log, Blueprint, graph, FurnaceBench results, labeling |
| `apps/web` | Next.js UI: landing, Blueprint, graph, Inference Lab, Guard, Evaluations, FurnaceBench, pricing |
| `packages/inference` | `furnace-bench`, standalone (no dependency on the rest of Furnace) |
| `packages/furnace` | extraction, reconstruction, Blueprint, evals, Forge, Guard, repair, GitHub, sandbox, jobs, CLI |
| `fixtures/` | F1 (`support-rag-py`, RAG + approval-gated tool on vLLM) and its scripted PR scenarios |
| `bench/` | FurnaceBench drivers, ground truth, results |
| `kernel_lab/` | Triton RMSNorm |
| `docs/` | [architecture](docs/architecture.md), [security](docs/security.md), [FurnaceBench](docs/furnacebench.md), [GitHub App](docs/github-app.md), [deploy](docs/deploy.md) |

## Quickstart (development, Windows/macOS/Linux)

```bash
uv sync
docker compose up -d postgres            # Postgres 17 on :5433
uv run poe migrate
uv run poe api                           # API on http://localhost:8010
cd apps/web && pnpm install && pnpm dev  # web on http://localhost:3000 (/api/* proxied to :8010)

# GPU lab (optional): vLLM serving Qwen2.5-0.5B-Instruct as "lab" on :8100
HF_HOME_HOST=$HOME/.cache/huggingface docker compose --profile gpu up -d vllm
```

Checks: `uv run poe check` (ruff, format, import-linter, pyright, pytest; the sandbox tests need
Docker). Web: `pnpm lint && pnpm exec tsc --noEmit` in `apps/web`.

## Runner commands

```bash
uv run furnace gh-check                                  # verify the GitHub App
uv run furnace gh-forge OWNER/REPO [--open-pr]           # Forge
uv run furnace gh-guard OWNER/REPO PR --suite FILE.py    # Guard check run
uv run furnace gh-repair OWNER/REPO PR --suite FILE.py [--open-pr]
uv run poe bench-gpu                                     # FurnaceBench GPU campaign (RQ4, RQ3, RQ5, report)
uv run poe kernel-correctness && uv run poe kernel-bench # Kernel Lab
```

GPU numbers depend on the laptop's power state: run on AC power and check the SM clock
(`nvidia-smi`) first. FurnaceBench GPU drivers refuse to run on battery.
