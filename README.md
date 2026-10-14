# Furnace

[![ci](https://github.com/dilipna/Furnace4LLM/actions/workflows/ci.yml/badge.svg)](https://github.com/dilipna/Furnace4LLM/actions/workflows/ci.yml)

**Ship prompt changes without slowing down your AI.**

Furnace tests each pull request of a Python LLM application on the team's own model server.
It blocks changes that make responses slower (for example, a prompt edit that stops the
server reusing its prompt cache) and drafts a fix it has already tested, for a person to
review. It is built for small teams that serve their own models (measured on vLLM). Eval
platforms such as promptfoo or LangSmith also record latency; Furnace is a narrower,
packaged workflow: both revisions' real prompts, interleaved on the same server, an interval
decision, the server's cache hit rate, the responsible line, and a fix checked by the same
gate.

The workflow: **connect** a repository through a GitHub App → **baseline** main's real
prompts on the team's endpoint → **inspect** a PR and select only the checks it can affect →
**gate** it on geometric-mean TTFT with a run-level 90% interval (PASS / BLOCK /
INCONCLUSIVE) → **repair** a supported regression (failing test first, rule-based fixes,
sandbox and gate) → **review**: a draft PR that a human merges or closes.

- **Guard** is the product: the check, the gate and the repair loop.
- **Scan** maps an app's call sites, prompts, models and serving settings from source (the
  graph Guard uses). Its findings are advisory: on five unseen apps 39 of 77 were right.
- **Forge** sets the checks up as a draft PR, sandbox-validated first.

## Verification status (2026-10-14)

| level | status | evidence |
|---|---|---|
| Local, end to end on fixture apps | **verified** | browser rehearsals 6/6 (`docs/demo-shots/rehearsal-2026-10-14b/timings.json`): scan, graph, live benchmark 80/80, live Guard run flags R1; screen recording `apps/web/public/demo/furnace-demo.webm` |
| Real GitHub (App, webhook, check run, draft repair PR) | **not yet**: passed tests against a mock GitHub; demo repository `dilipna/furnace-demo-f1` is populated; the App is being created | `scripts/live_github_run.py`, `scripts/live_github_verify.py` write `bench/results/<date>-live-github/` |
| Hosted deployment | **not deployed**; the production API image passed `scripts/smoke_hosted.py` locally | `docs/deploy.md` |
| Production readiness | **no** (no accounts or organizations, no per-tenant isolation) | `docs/pilot.md` |

Pilot setup and limits: **[docs/pilot.md](docs/pilot.md)** · founder materials:
**[docs/founder/](docs/founder/brief.md)**.

Every number in this repository comes from a documented command; negative results and
corrections are reported. See **[FurnaceBench](docs/furnacebench.md)**, the reports in
`bench/results/<date>/`, the dated `CORRECTIONS.md` shown on the `/bench` page, and the
**[claims ledger](docs/claims.md)**. Short **[case study](docs/case-study.md)** ·
three-minute **[demo script](docs/demo-3min.md)** · final
**[acceptance checklist](docs/completion.md)**.

**Deterministic vs model-powered.** Scan, Forge, Guard's impact analysis, the perf gate and
repair are deterministic (AST and config analysis, graph diffs, load generation, run-level
interval statistics, rule-based AST edits). The only model in the loop is the one being served and
measured; an LLM judge is built but not calibrated (no labels or key yet).

## Measured so far (laptop RTX 3050 Ti, vLLM, Qwen2.5-0.5B)

| question | result | source |
|---|---|---|
| Does Scan find LLM call sites in apps it has never seen? | On each held-out set's **first** scan (labels committed before it): recall **4/34** call sites (12%; per set 0/8, 1/5, 1/9, 2/9, 0/3), precision 4/4. After fixes made for those misses, the same 34 labels: 33/34 at precision 33/33 (a fit to apps the scanner was changed for, not a held-out result). Misses at first scan were unsupported SDKs, script-level calls and, in the newest sets, agent runners (OpenAI Agents SDK) and clients held in containers. Precision is 1.00 for call sites and routes only; prompts, workflows and contradictions have false positives. **Held-out set 6** (five apps picked by a fixed search, scanner frozen, labels committed before the scan): call sites **32/48** found, 32/32 correct (per app 24/27, 5/12, 3/5, 0/3, 0/1); Blueprint findings **precision 39/77, recall 39/64**, while **148/148** evidence links resolved, so link validity says nothing about correctness. Labels by the developer agent, not independently reviewed | `bench/results/2026-10-12-reconcile/scanner_reconciliation.md`, `bench/results/2026-10-13-set6/NOTES.md` |
| Does it stay safe on code it does not understand? | Held-out set 4, first run: docs-only and unrelated-code PRs selected no checks (6/6); an injected prompt regression was fully handled in 0/3 apps on first run, 3/3 after two fixes (no longer held-out); Forge refused with a reason where it could not slice a harness and opened no PR without a green sandbox run. Evidence links of findings are internally consistent (10/10 items on the first run; 20/20 now, 1 of them a file-existence check); that is not a measure of whether a finding is right, which no label set measures | `bench/results/2026-10-11-external/`, `2026-10-12-reconcile/` |
| How large is a prompt-cache regression? | R1 (request id at the top of the system prompt): p95 TTFT **+905% to +1,004%**, prefix-cache hit 98% -> 0% | `bench/results/2026-10-09-gate-warmup-v2/rq5.md` |
| Can Furnace repair it without making things worse? | Under the frozen gate (G3): **verified in 3/3 repeated trials of one supported scenario** (fixture F1, regression R1, two rule strategies in fixed order), not a rate over apps or regressions. Each time the generated regression test failed on the PR and passed on main; the first strategy was rejected (INCONCLUSIVE once, BLOCK at +37.8% and +39.6%); the second (log the request id and timestamp instead of sending them) passed at +4.2%, +0.9%, +1.7% vs main (90% intervals up to +9.5%) and -85.5%, -85.6%, -86.0% vs the PR (intervals entirely below 0, as the acceptance rule requires), prefix-cache hit back to 98%, and rendered byte-identical prompts to main for 34/34 questions. Every executed audit check passed; the LLM judge was skipped (no key; not part of the acceptance rule). R2 (context bloat) is refused as unsupported. Under the gate in use until 2026-10-12 the same loop verified 1/3 (`2026-10-12-gate-ci/rq5.md`); the two are not pooled. No LLM strategy | `bench/results/2026-10-12-gate-validation/rq5.md`, `NOTES.md` there |
| How noisy is the perf gate, and what does it decide on? | The gate was redesigned on 2026-10-12 and the design frozen before implementation: it decides on **geometric-mean TTFT** with the **run** as the unit and a **90% Welch interval** (p95 is reported, not decisive; a p95 over 34 requests cannot confirm a 10% tolerance). On the 20 earlier A/A trials, used to choose the rule, it gives PASS 87% / INCONCLUSIVE 13% / false FAIL 0% (optimistic: chosen there). Fresh validation, rule unchanged (63 trials recorded = 60 counted + 3 affected and replaced, all on AC, 780-828 MHz; every trial in `validation/trials.md`): unchanged code (V1 24 + V2 12, as planned before any trial) **false FAIL 0/36** (exact 95% CI 0-9.7%), PASS 29/36, INCONCLUSIVE 7/36; the R1 regression **BLOCK 6/6**. The graded regressions measured only +4% to +7% inside the gate (their calibration had said +13%, +18%, +30%), so they came out INCONCLUSIVE 15/18 and PASS 3/18: detection of regressions just above the 10% tolerance is **not shown**. A latency-location gate, not a tail-SLO gate; p95 reported separately | `docs/gate-revision.md`, `bench/results/2026-10-12-gate-validation/validation/report.md` and `NOTES.md` |
| Does Guard save time? | 13 PRs: ran 46% of checks, caught 3/3 full-suite failures, same conclusion 13/13 | `bench/results/2026-10-06/rq3.md` |
| What does prefix caching buy on the real workload? | caching off raised p95 TTFT in all 15 cells, same sign in every paired repeat: +193% to +433% at max-num-seqs 32 (median per cell), +96% to +433% across all configs | `bench/results/2026-10-06/rq4/rq4.md` |
| Triton RMSNorm kernel | correct 36/36; at parity with `torch.compile` (both ~9.8x eager, 99% of copy bandwidth) | `kernel_lab/results/2026-10-09/` |

## What works today

| area | status |
|---|---|
| Scan of public GitHub repos / ZIPs: Python code (OpenAI, Anthropic, Groq, Ollama, LiteLLM, Cohere, Mistral, Google, Hugging Face, Bedrock, Replicate, llama.cpp, LangChain, OpenAI Agents SDK incl. agent instructions), routes, Streamlit/CLI workflows, Blueprint, contradictions, graph | working; other languages are reported as not analyzed (their configs and docs still are) |
| Live views: lab telemetry (vLLM /metrics + NVML), "Run it now" benchmark, Guard run streamed check by check, graph path trace, scan terminal | working locally; hosted deploys show the recorded runs, labeled |
| `furnace-bench` load generator (TTFT/TPOT/goodput, CIs, telemetry, mock-validated) | working |
| Inference Lab: prefix-cache and scheduler sweep on the real F1 workload; TTFT vs vLLM queue correlation | working (RQ4; correlation from the stored RQ4 runs, `bench/results/2026-10-12-correlation/`) |
| Inference Lab optimizer: quality-constrained choice of model, prefix caching and max-num-seqs | measured (8 configs, design fixed first, [optimizer](docs/optimizer.md)): **keep the baseline**; the top config's independent rerun was inconclusive (goodput +3.8%, 90% interval -8.8 to +18.2) (`bench/results/2026-10-12-optimizer/NOTES.md`) |
| Guard: graph-targeted checks, perf gate on geometric-mean TTFT with a run-level 90% interval (PASS / WARN / BLOCK / INCONCLUSIVE; p95 advisory), local runs and GitHub check runs | working locally; the GitHub path is tested against a mock API, **not yet run against live GitHub** (needs the [App](docs/github-app.md)) |
| Repair of prompt-prefix regressions: two rule strategies tried in order, interval-based acceptance, decision record in the PR | one supported scenario (F1, R1): 3/3 repeated trials verified under the frozen gate; other regression types are refused; LLM-patch strategy not built |
| Forge change set (evals, prompt extraction, benchmarks, CI gate), sandbox-validated | working on F1 and planned on 1 of 3 external apps (set 4); draft-PR path not yet run live |
| GitHub integration: App from a manifest (`furnace gh-setup`), idempotent draft PRs and check runs, webhooks once per delivery (push or `gh-poll` from the App's delivery log), installation isolation, fenced job leases and timeouts, consent-gated repair jobs (a draft PR only after the regression test, the existing tests and the perf gate pass) | built and tested against a mock GitHub (`poe adversarial` for the attack paths); **live run pending** |
| Deterministic evals; human labeling queue | working; LLM-judge calibration needs a BYOK key and labels |
| Hosted control plane (Vercel + Render + Supabase) | **deferred for this release** (owner decision, 2026-10-13); deploy files exist ([guide](docs/deploy.md)) but were never deployed |
| Not built: TypeScript/JS extraction, VLM image evidence, LLM-patch repair, auth/orgs, BYOK storage, LLM synthesis, Stripe. Experimental (stored, kept out of the default Blueprint): the tool approval-boundary rule, which flags side-effecting functions no model can call (set 6) | see [scope](docs/scope.md), [security](docs/security.md) and FurnaceBench "Not run" |

## Layout

| path | what |
|---|---|
| `apps/api` | FastAPI: scans, SSE logs, Blueprint, graph, live lab telemetry and runs, Guard runs, FurnaceBench results, labeling |
| `apps/web` | Next.js UI: landing, pilot onboarding, Blueprint, graph, Inference Lab, Guard, Evaluations, FurnaceBench |
| `packages/inference` | `furnace-bench`, standalone (no dependency on the rest of Furnace) |
| `packages/furnace` | extraction, reconstruction, Blueprint, evals, Forge, Guard, repair, GitHub, sandbox, jobs, CLI |
| `fixtures/` | F1 (`support-rag-py`, RAG + approval-gated tool on vLLM), F2 (`agent-actions-py`, tool-calling agent) and their scripted PR scenarios |
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
Before pushing, run the CI jobs in Linux on the committed tree: `bash scripts/ci_linux.sh`
(non-root user, sandbox tests included; Windows runs miss Linux-only failures).

## Runner commands

```bash
uv run furnace gh-setup --name furnace-dev-<you>         # create the GitHub App from its manifest (2 clicks)
uv run poe gh-poll                                       # webhook events from the App's delivery log
uv run furnace gh-check                                  # verify the GitHub App
uv run python scripts/live_github_run.py --repo OWNER/furnace-demo-f1   # the whole live run, recorded
uv run furnace gh-forge OWNER/REPO [--open-pr]           # Forge
uv run furnace gh-guard OWNER/REPO PR --suite FILE.py    # Guard check run
uv run furnace gh-repair OWNER/REPO PR --suite FILE.py [--open-pr]
uv run poe bench-gpu                                     # FurnaceBench GPU campaign (RQ4, RQ3, RQ5, report)
uv run python bench/gate_noise.py                        # perf-gate A/A noise characterization
uv run python bench/external_validation.py --sandbox     # Scan/Forge/Guard on held-out set 4
uv run poe adversarial                                   # attack-path regression tests only
uv run poe kernel-correctness && uv run poe kernel-bench # Kernel Lab
uv run python scripts/rehearse.py [--video DIR]          # rehearse the demo path in a browser
```

GPU numbers depend on the laptop's power state and on the clock the driver picks for this light
serving load (780 MHz on Oct 6-9, ~1,960 MHz on Oct 11 after a reboot; never throttled), so every
result records its clock and comparisons are made only inside a set that shares one
(`bench/results/2026-10-11-live-clock/`). FurnaceBench GPU drivers refuse to run on battery.
