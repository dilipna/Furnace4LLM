# Demo script (about 4.5 minutes) and pre-flight checklist

Every number shown comes from `bench/results/`; say "measured on a laptop RTX 3050 Ti" when
showing latency, and mention the clock cap noted in the campaign NOTES if asked.

## Pre-flight (30 minutes before)

- [ ] Laptop on AC; OMEN/Windows power mode on performance; `nvidia-smi` shows the GPU clock
      above 1,500 MHz under load (otherwise say "power-capped laptop" when showing latency).
- [ ] Docker Desktop running; `docker compose up -d postgres`; lab vLLM up
      (`HF_HOME_HOST=... docker compose --profile gpu up -d vllm`), `curl localhost:8100/v1/models` works.
- [ ] API `uv run poe api` (:8010) and web `pnpm dev` (:3000) running, or the hosted URLs open.
- [ ] `uv run furnace gh-check` prints the App and the `furnace-demo-f1` installation.
- [ ] Demo repo has the R1 PR open (docs/github-app.md, step 4) and Guard has already run once on
      it (the live run takes ~2-4 minutes; show the finished check run, re-run only if time allows).
- [ ] Browser tabs: landing, the F1 scan Blueprint, its graph, /lab, /guard/r1_dynamic_head,
      /bench, the demo repo's PR and the repair draft PR.
- [ ] Fallback: screenshots of every tab in `docs/demo-shots/` (regenerate with
      `uv run python scripts/demo_shots.py` while the stack runs) and a screen recording.

## Script

1. **(0:00) Problem.** "You already built the AI app. Nobody can tell you whether the next PR
   makes it slower or wrong." Show F1: FastAPI RAG support assistant on vLLM, with an
   approval-gated ticket tool.
2. **(0:30) Scan.** Paste `github.com/<you>/furnace-demo-f1` on the landing page; the live stage log streams; the
   Blueprint shows the vLLM + Qwen endpoint with evidence chips, the README-vs-code model
   contradiction, the approval gate on `create_ticket`, and the prefix-stability finding.
3. **(1:20) Graph.** Open "Graph →"; click the `POST /chat` workflow; the highlighted path runs
   through the handler, the system prompt, the model, the endpoint and the vLLM serving flags.
4. **(1:45) Inference Lab** (`/lab`). F1's fingerprint from 89 real traces (965-token prompts,
   857-token shared prefix); prefix-cache hit predicted 89.0% vs measured ~89%; the sweep: turning
   prefix caching off multiplies p95 TTFT several-fold at every concurrency (paired repeats,
   same sign every time); max-num-seqs 8 collapses SLO goodput at concurrency 16.
5. **(2:40) Forge.** Show the Forge draft PR on the demo repo: the manifest table (each file with
   its reason, target and risk), the extracted prompt (byte-identical), installed tests.
6. **(3:10) Guard.** Open the R1 PR ("request id in the system prompt for debugging"): the Furnace
   Guard check fails; it ran a subset of the suite with reasons for what it skipped; the perf
   table shows p95 TTFT and prefix-cache hit rate collapsing; the annotation points at the line.
7. **(3:45) Repair.** `/guard/r1_dynamic_head` timeline: regression test written first (fails on
   the PR, passes on main), localized hunk, rule-based fix, sandbox validation, perf gate, full-
   suite audit, and the draft repair PR on GitHub. "A human merges. Furnace never touches production."
8. **(4:15) Evidence** (`/bench`). RQ1 held-out scanner recall including the miss (unseen SDKs),
   RQ3 recall at the share of the suite executed, RQ5 verified repairs, the negative results. Close.

## If something fails live

| failure | fallback |
|---|---|
| GitHub scan rate-limited | show the scan of the same repo done earlier (keep its URL) |
| vLLM not ready / GPU busy | /lab and /guard read stored results; say so |
| Guard run slow | show the completed check run; the CLI log has the timings |
| Network down | local stack + screenshots in `docs/demo-shots/` |
