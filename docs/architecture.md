# Architecture

```
                 ┌──────────── hosted control plane (free tiers) ─────────────┐
 browser ──► Vercel: apps/web (Next.js) ──/api/*──► Render: apps/api (FastAPI)  ──► Supabase Postgres
                 │   landing, Blueprint, graph,          │ scans, SSE, bench API      jobs (SKIP LOCKED),
                 │   Lab, Guard, Evals, Bench            │ embedded cpu worker        scans, facts, graph
                 └───────────────────────────────────────┴────────────────────────────────────────────┘
 laptop runner (GPU + Docker):  furnace CLI / worker ─► sandbox (Docker) ─► lab vLLM (:8100, internal net)
                                 Forge · Guard · repair · FurnaceBench · Kernel Lab ─► GitHub App (draft PRs, checks)
```

## Packages

| package | role |
|---|---|
| `packages/inference` (`furnace-bench`) | standalone load generator for OpenAI-compatible servers: SSE client, TTFT/TPOT/ITL, closed/open loop, bootstrap CIs, SLO goodput, vLLM/SGLang/Ollama adapters, Prometheus + NVML telemetry, mock server, trace fingerprinting. No dependency on the rest of Furnace (enforced by import-linter). |
| `packages/furnace` | everything else, below |
| `apps/api` | FastAPI: public scans + SSE log, Blueprint, graph, FurnaceBench results, labeling |
| `apps/web` | Next.js 16 UI on the same data |
| `bench/` | FurnaceBench drivers (RQ1-RQ5), ground truth, results |
| `kernel_lab/` | Triton RMSNorm, correctness, benchmark |

## Inside `furnace`

1. **Ingest** (`ingest/`, `security/safe_extract`): GitHub tarball or ZIP into a temp dir with
   traversal, link, size and ratio limits.
2. **Extract** (`code_intel/`): Python AST facts (LLM clients and call sites incl. module-level
   scripts and LangChain models, prompts and their dynamic segments, retrievers, routes,
   side-effecting tools and approval gates, config reads, call graph), plus configs, compose
   files, dotenv, prompt files and docs claims. Every fact carries a locator and a redacted excerpt.
3. **Reconstruct** (`reconstruction/`): noisy-OR reconciliation of candidates from code, config
   and docs into claims with confidence; contradictions kept, never silently resolved; AppSpec
   and the behavior-to-code graph (workflows → capabilities → code → prompt/model/endpoint/tools
   → config).
4. **Blueprint** (`blueprint/rules.py`): evidence-triggered findings; a finding resolves only
   when its verifying artifact exists in the repository.
5. **Forge** (`forge/`): harness slicing of the app's own handler, templates and codemods, then
   sandbox validation (prompts byte-identical, installed + existing tests pass) before any PR.
6. **Evals** (`evals/`): deterministic checks, judge specs, calibration (TPR/TNR, Rogan-Gladen).
7. **Guard** (`guardian/`): diff → touched graph nodes → selected checks with reasons; executors
   (unit, security, prefix stability, citation contract with Fisher test, context budget, perf
   gate with interleaved repeats); check-run rendering.
8. **Repair** (`guardian/repair/`): failing test first (must fail on head, pass on base),
   localization to hunks, rule strategy, sandbox validation, perf gate, draft PR.
9. **GitHub** (`github/`): App JWT, per-job scoped tokens, atomic draft PRs, check runs, webhook
   HMAC; `github/flows.py` runs Forge / Guard / repair end to end for the CLI.
10. **Jobs** (`jobs/`): Postgres queue with `SKIP LOCKED`, leases and heartbeats; `cpu` queue in
    the API process, `runner` queue on the laptop.

## Why these choices

- One Postgres instead of Redis/Kafka/Neo4j: the graph is small per scan; `networkx` traverses it.
- GPU and sandbox work stays on hardware the user controls; the hosted part needs no secrets
  from customer repositories beyond a scoped, short-lived token.
- Deterministic first: every claim can be traced to a file and line; LLM synthesis (not built
  yet) may only add candidates, never overwrite code-derived ones.
