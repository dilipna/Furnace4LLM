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
   gate with rotated interleaved repeats and a 95% interval: PASS, WARN, BLOCK or INCONCLUSIVE);
   check-run rendering.
8. **Repair** (`guardian/repair/`): failing test first (must fail on head, pass on base),
   localization to hunks, rule strategy, sandbox validation, perf gate, draft PR.
9. **GitHub** (`github/`): App from a manifest (`setup.py`), JWT, per-job scoped tokens,
   idempotent draft PRs and check runs, webhook ingestion exactly once (`events.py`, by push
   or by reading the App's delivery log in `deliveries.py`); `flows.py` runs Forge / Guard /
   repair end to end for the CLI and the runner jobs (`jobs.py`).
10. **Jobs** (`jobs/`): Postgres queue with `SKIP LOCKED`, fenced leases, heartbeats, timeouts
    and dedupe keys; `cpu` queue in the API process, `runner` queue on the laptop.

## The event path, end to end

```
PR opened/pushed ─► GitHub ──push──► API /api/github/webhook (HMAC, size, shape) ─┐
                           └─log───► runner `gh-poll` (App JWT, delivery log) ─────┤
                                                                                   ▼
          events.ingest: webhook_deliveries row per GUID (replays are no-ops, audit outcome)
                         enqueue_once guard.pr  dedupe key guard.pr:<repo>#<n>@<head sha>
                                                                                   ▼
 runner claims (SKIP LOCKED, fenced by worker+attempt, heartbeat, timeout 30 min)
   guard_pr: installation check ─► PR head still the event's? (else superseded)
             ─► existing check run on this head? (reuse / take over) ─► tarballs (safe extract)
             ─► impact on both graphs ─► selected checks in the sandbox ─► perf gate (95% CI)
             ─► check run (success / neutral / failure) + supported regression signatures
                                                                                   ▼
   failure + signature + FURNACE_GUARD_AUTO_REPAIR ─► enqueue_once repair.pr (one per head)
   repair_pr: failing test first ─► strategies in order ─► sandbox tests ─► perf gate
              (faster than the PR with 95% confidence, worst case vs base < block threshold)
              ─► draft PR into the PR branch (idempotent) with the decision record
```

## Job lifecycle

`queued` → `running` (claimed: `attempts+1`, `locked_by`, `heartbeat_at`) → `succeeded` |
`failed`, or back to `queued` with exponential backoff while attempts remain. Every write after
the claim is conditioned on `(locked_by, attempts)` still holding: if a worker stalls past the
lease and another claims the job, the first worker's heartbeat finds the row gone and cancels
its handler, and its late completion or failure is refused. A job whose heartbeat stopped
with no attempts left is failed by the reaper; a worker restarted mid-job fails its own
orphans on start. Each kind has a timeout (`jobs.timeout_s`, default 1 h); handlers emit
`job_events` (stage, message, structured data) that the UI streams. Side effects are
idempotent at the GitHub layer as well, so a retried attempt cannot open a second PR or
post a second check run.

## Why these choices

- One Postgres instead of Redis/Kafka/Neo4j: the graph is small per scan; `networkx` traverses it.
- GPU and sandbox work stays on hardware the user controls; the hosted part needs no secrets
  from customer repositories beyond a scoped, short-lived token.
- Deterministic first: every claim can be traced to a file and line; LLM synthesis (not built
  yet) may only add candidates, never overwrite code-derived ones.
