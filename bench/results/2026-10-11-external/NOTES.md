# 2026-10-11: held-out set 4, Scan + Forge + Guard on three independent apps

Labels and the validation driver (with its expected outcomes) were committed in `f0fce9d`
before any scan. No scanner or reconstruction code changed between that commit and the
first scan, so `rq1_set4_first_scan.*` and `external_validation_first_run.*` are held-out
results. Apps (MIT, pinned commits in `bench/ground_truth/`): rag-postgres-openai-python
(FastAPI, pgvector hybrid RAG, OpenAI Agents SDK), tech-trends-chatbot (FastAPI + SSE, Redis
vector store, tool calling; a different author), openai-chat-backend-fastapi (minimal
Responses API backend).

## Scan (RQ1, `rq1_set4_first_scan.md`)

| category | held-out set 4 | for comparison: set 3 (2026-10-09) |
|---|---|---|
| LLM call sites | **2/9 recall, precision 1.00** | 8/9, precision 1.00 |
| routes | 10/13, precision 1.00 | |
| serving engine | 2/3 | |
| models | 0/6 | |
| retrievers, tools | 0/2, 0/2 | |
| attribute accuracy | 25/26 (empty scan: 15/21) | |

Why calls were missed (each is a construct the extractor does not resolve today):
- rag-postgres: all five generation calls go through the OpenAI Agents SDK
  (`Runner.run` / `Runner.run_streamed` with `Agent(instructions=...)`).
- openai-chat-backend: the client is held in a module-level dict
  (`clients["openai"].responses.create`).
- Models: values come from `os.getenv(..., default)` branches and pydantic-settings field
  defaults; none were read.

Prompts score low partly by labeling convention: the scanner reported the prompt files
(`prompts/answer.txt`) and per-call system slots; the labels name the Python attributes that
load the files. By the matching rule fixed before scoring these count as misses and false
positives; the labels were not changed after the scan. The report table was re-rendered
after a header fix (set 4 column was unlabeled); the numbers were verified identical.

## Source links, Forge, Guard (`external_validation*.md`)

- Source links: every file evidence of every finding resolves to the file and line range
  and contains its excerpt: 10 checked, 0 broken.
- Guard on synthetic PRs (expected = correct behavior, fixed before the run): docs-only and
  unrelated-code changes selected nothing, correct in 6/6. The prompt change (a per-request
  value prepended to the system prompt) was fully correct in 0/3: the prefix check and the
  prefix-instability signature were found in 2/3 apps, but the perf gate was not selected
  (no workflow reaches the prompt: the call sites above are missed, or the route reaches the
  LLM through `asyncio.create_task`); in rag-postgres the Agents SDK instructions were not
  recognized as a system prompt at all.
- Repair applicability: both strategies apply on openai-chat-backend and make the prompt
  prefix-stable again (re-analyzed); in tech-trends the system message is built in
  `__init__` and used elsewhere, which the strategies do not handle.
- Forge: plans 7 files on tech-trends (timeout test, prompt extraction, CI gate); 0 on the
  others, each with the reason (no harness: control flow before the messages are built /
  no route reaches the system-message builder; timeouts not installable on clients created
  inside factory functions). Forge refuses rather than guesses.
- Sandbox validation (run 2, `_sandbox_before_deps_fix`): failed on all three because the
  sandbox only installed a root `requirements.txt`; these apps keep requirements in
  `src/`, `src/backend/` (included from a root `requirements-dev.txt`) or Poetry only.
  **Fix (Furnace change, so later Forge-validation numbers on set 4 are "after fixes"):**
  the sandbox now installs the root `requirements-dev.txt` or `requirements.txt` with every
  `-r`/`-c` include that stays inside the repository (escapes refused, tested).
- Run 3 (`external_validation.md`, after the fix): openai-chat-backend's own test suite now
  runs in the sandbox, 5 passed and 1 failed (`test_chat_stream`, a snapshot mismatch on
  the unmodified code at the pinned commit: pre-existing, with `openai>=1.108.1`
  unpinned); Forge requires a green baseline, so no PR. rag-postgres: dependency install
  fails building psycopg2 from source in the slim image, and its tests need a live
  Postgres, which a network-less sandbox cannot provide. tech-trends: Poetry-only
  dependencies are not installed; no PR.

## What this says

Furnace generalizes where code calls an LLM SDK directly (set 3: 8/9) and degrades sharply
on indirection that is common in newer apps (agent frameworks, clients in containers,
background tasks): 2/9. It fails safe: no false positives on call sites or routes, no
wrong selections on unrelated PRs, Forge refusing with reasons, and no PR without a green
sandbox run. The next scanner work, measured on a new held-out set afterwards: Agents SDK
calls and instructions, subscripted clients, `create_task` edges, env/settings defaults.

## After fixes (set 4 is no longer held-out for these)

1. Sandbox dependency install (above): `external_validation_after_deps_fix.*`.
2. Guard selection: a detected prefix-instability signature now selects the benchmarks
   whose triggers include prompt changes even when no traced workflow reaches the prompt
   (`guardian/impact.py`, `lost_stable_prefix`). `external_validation.md`: the prompt
   scenario is correct in 2/3 apps (was 0/3), all scenarios 8/9; the remaining miss is
   rag-postgres, whose Agents SDK `instructions` are not recognized as a system prompt (a
   scanner gap, not a selection gap). F1's impact tests are unchanged.
