# Scope: the agreed acceptance criteria and where each stands (2026-10-12)

Source of the criteria: the approved plan,
`C:\Users\user\.claude\plans\pasted-content-id-65d9-you-are-streamed-falcon.md`:
the Outcome (top), the per-day **Accept** lines (§15), the MUST / SHOULD / LATER / CUT table
(§16) and the end-to-end Verification list. The Oct 12 audit called some MUST items
"optional" in its remaining-work list; that was a silent downgrade and is withdrawn here.
Nothing below is dropped without being named as a deviation.

Status words: **done** (built, and the evidence column shows it running), **done locally**
(works on this machine; the live/hosted part is not yet shown), **partial**, **blocked** (needs
an action only you can take), **not built**.

## Outcome criteria

| criterion (plan, Outcome) | status | evidence | decision |
|---|---|---|---|
| One vertical slice: Scan → Blueprint → Inference Lab → Forge PR → Guard check → Repair draft PR | done locally; **GitHub half blocked** | local: `scripts/rehearse.py`, `docs/demo.md`; live: `scripts/live_github_run.py` + `scripts/live_github_verify.py` ready, not run | retained; needs your GitHub App (below) |
| Proven on 2 fixture apps + 1 real OSS repo | **in progress**: F1 + F2 (`agent-actions-py`, Python, built 2026-10-13, not yet scanned or Guarded in a recorded run) + 19 labeled OSS apps in 6 held-out sets | `fixtures/apps/agent-actions-py/`, `docs/scanner-eval-set6.md` | retained: the second fixture is Python (D1 as signed off) |
| FurnaceBench results from documented commands | done | `docs/furnacebench.md`, every result folder records its command and commit | retained |

## MUST items (plan §16)

| item | status | evidence / gap | decision |
|---|---|---|---|
| GitHub / ZIP / README / text ingestion, safe extraction, secret redaction | done for GitHub tarball, ZIP upload, README; **free-text evidence not built** | `tests/test_security.py`, `poe adversarial`; clean-clone public scan 2026-10-12 | text input: deviation D1 (no consumer without the LLM/VLM path) |
| Python extractors (full); TS (call sites, tools, routes) | Python done (stdlib `ast`, not tree-sitter); **TS not built** | recall limits in `scanner_reconciliation.md` | TS: deviation D1 |
| Screenshots / diagrams via VLM → claims | **not built** | – | deviation D1 |
| JSONL traces → WorkloadSpec | done | `furnace_bench/fingerprint.py`, W1 in `2026-10-04-f1-quality/` | retained |
| Evidence / Claim / confidence / contradictions | done (contradiction recall is low on held-out apps: 0/5 first scan, 1/5 now) | `scanner_reconciliation.md` §3 | retained, limit stated |
| Graph in Postgres + networkx traversal | done | `/scans/<id>/graph` | retained |
| Blueprint rule engine + UI + share link | engine and UI done; **no separate share endpoint** (the public scan URL is unguessable and is what gets shared) | `routers/scans.py` | partial: accepted as is |
| Anonymous public-repo scan | done | clean-clone smoke 2026-10-12 (scan in 3 s, 4 findings) | retained |
| furnace-bench: SSE, TTFT/TPOT/ITL, sweeps, goodput, CIs, reports | done | `packages/inference/tests/` | retained |
| Mock-server measurement validation | done | `test_mock_accuracy.py` | retained |
| Adapters vLLM / OpenAI-compatible / Ollama | vLLM measured; **Ollama adapter has never been run against Ollama** | `adapters/engines.py`; no Ollama result exists | partial: Ollama claim removed |
| NVML + Prometheus telemetry + correlation | done (correlation added 2026-10-12, descriptive) | `2026-10-12-correlation/correlation.md` | retained |
| Lab launcher (docker vLLM configs) | done as a bench launcher (pinned image, fresh container per config); not a product runner job | `bench/rq4.py launch`, `bench/optimize.py` | partial: accepted |
| Prefix caching optimization end to end | done | RQ4, R1, repair | retained |
| Batching / scheduler optimization | measured (RQ4) and part of the optimizer grid | RQ4 `max-num-seqs` | retained |
| Quality-constrained optimizer (grid + Pareto) | **built and unit-tested; grid not measured yet** (needs ~45 GPU minutes on AC: `bench/run_remaining_gpu.sh`) | `docs/optimizer.md` (design fixed before measuring), `furnace/optimizer.py`, `bench/optimize.py` | retained |
| 8 deterministic checks + per-failure-mode judges + calibration | checks done (8); judge and Rogan-Gladen calibration built; **judge never run, 0/60 items labeled** | `evals/checks.py`, `rq2.md` §3 | blocked on you: 60 labels and a Groq key |
| Labeling UI (minimal) | done | `/evals`, `bench/label.py` | retained |
| Forge: templates + libcst codemods + sandbox validation + draft PR + patch | done locally (sandbox-validated on F1); **live draft PR not yet opened** | `test_forge.py` | blocked on the GitHub App |
| GitHub App, scoped tokens, write consent, webhooks, Checks API | built, mock-tested, verifier written; **never run against GitHub** | `live_github_verify.py` checks every property you listed | blocked on the GitHub App |
| Guard impact analysis + targeted selection + perf gate | done locally; gate statistic revised (design frozen first); **fresh validation partial**: unchanged code 14/24 trials (0 false FAIL); other sets and RQ5 under the new gate not run yet | `docs/gate-revision.md` | retained |
| Repair loop R1 (rule + LLM strategies) | rule strategies done; **LLM-patch strategy not built** | RQ5 | deviation D2 (the plan's own fallback) |
| FurnaceBench RQ1-RQ5 + reproducible commands | done, with gaps: RQ1 has no F2; RQ2 has no judge or human labels; RQ4 has no Ollama or T4 point; RQ5 has no LLM strategy | `bench/results/` | retained, gaps stated |
| Kernel Lab Triton RMSNorm (laptop) | done (36/36 correct; parity with torch.compile) | `kernel_lab/results/2026-10-09/` | retained |
| Hosted control plane (Vercel / Render / Supabase) | **not deployed**; API image builds in CI | `docs/deploy.md`, CI `image` job | blocked on your accounts |
| Pricing page | done | `/pricing` | retained |

SHOULD items, all cuttable under the plan: built: open-loop arrivals, SGLang adapter (never
run), graph page. Not built: URL inspection, OpenAPI import, OTel/Langfuse import, video,
AWQ on T4 (an AWQ model is in the laptop optimizer grid instead), `vllm bench serve`
cross-check, note clustering, Kernel Lab on T4, Postgres RLS, Stripe test checkout, repair
R2 (attempted in RQ5: rejected at diagnosis, since R2 is not a prefix-instability regression).

## Decisions (signed off by the owner on 2026-10-13)

- **D1, approved with a change:** TypeScript extraction, VLM image claims and free-text
  evidence are deferred to after the MVP, and every claim says **Python apps only**. The
  second fixture stays in the completion criteria, as a **Python** fixture: F2
  `agent-actions-py` follows the plan's F2 specification (tool-calling agent, read / write /
  external tools, no evals, no tracing, R4 approval removal) with two stated departures (the
  planted missing gate is on `send_email`; the cache-layer contradiction is in text, not a
  diagram). See its `ground_truth.yaml` header.
- **D2, approved:** repair is rule-based for the documented supported case (prompt-prefix
  instability on F1); no LLM-patch strategy in the MVP. Claims say "rule-based repair".
- **Retained, blocked on you:** GitHub App + demo repository (live slice), 60 labels + a Groq
  key (judge calibration), Vercel/Render/Supabase accounts (hosted control plane).
