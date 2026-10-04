# Furnace

**Make your LLM faster without breaking it.**

Furnace is an inference-reliability retrofit for LLM applications that already exist. It reconstructs
an app from its code, docs, screenshots, traces and endpoints into a *behavior-to-code reliability
graph*, then installs targeted evals and serving benchmarks, and guards every PR against quality and
performance regressions (TTFT, TPOT, SLO goodput).

> Status: under active development (v0.1, October 2026). Every number in this repository is produced
> by a documented command; see `bench/` and `docs/furnacebench.md` once published.

## Layout

| Path | What |
|---|---|
| `apps/api` | FastAPI control plane |
| `apps/web` | Next.js product UI |
| `packages/inference` | `furnace-bench`: standalone async streaming benchmark for OpenAI-compatible servers |
| `packages/furnace` | reconstruction, graph, evals, forge, guard |
| `fixtures/` | benchmark applications with ground truth |
| `bench/` | FurnaceBench drivers and results |
| `kernel_lab/` | Triton RMSNorm experiment |

## Quickstart (dev)

```bash
uv sync
uv run poe db-up && uv run poe migrate
uv run poe api          # http://localhost:8010
uv run poe runner       # laptop runner: GPU / sandbox jobs
cd apps/web && pnpm install && pnpm dev   # http://localhost:3000

# optional: local GPU inference lab (vLLM, Qwen2.5-0.5B-Instruct)
docker compose --profile gpu up -d vllm   # OpenAI-compatible on :8100
```
