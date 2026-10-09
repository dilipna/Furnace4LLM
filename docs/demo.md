# Demo script (about 5 minutes) and pre-flight checklist

Every number shown comes from the running system or `bench/results/`; say "measured on a laptop
RTX 3050 Ti" when showing latency. On this laptop the GPU has run at 780-900 MHz under load
even on AC (Windows "Balanced"); say "power-capped laptop" unless pre-flight shows more.

Timings below are from two full rehearsals on 2026-10-09 (`scripts/rehearse.py`, results and
screenshots in `docs/demo-shots/rehearsal-1/` and `rehearsal-2/`): every step passed both times.

| step (rehearsed in a browser) | rehearsal 1 | rehearsal 2 |
|---|---:|---:|
| landing loads, live lab panel connects | 1.8 s | 0.4 s |
| GitHub scan (Azure-Samples/openai-chat-app-quickstart) to Blueprint | 5.8 s | 3.7 s |
| graph: select the workflow, path trace finishes | 1.8 s | 1.7 s |
| /lab "Run it now": 80 requests, c = 1, 2, 4, 8 | 27.6 s | 32.5 s |
| /guard/r1_dynamic_head "Run Guard on this PR" to verdict | 85.5 s | 83.9 s |
| /bench | 0.4 s | 0.4 s |

Both Guard runs ended `FAILURE: 2 regressions found: prompt_prefix_stable, chat_perf_gate`
(p95 TTFT 205 → 1,030 ms, prefix-cache hit 98% → 0% in rehearsal 1). Not rehearsed yet: the
GitHub App steps (Forge PR, R1 PR check run, repair PR) — they need the App (docs/github-app.md).

## Pre-flight (30 minutes before)

- [ ] Laptop on AC; OMEN/Windows power mode on performance. Under load check
      `nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv`; if it still shows ~780 MHz,
      say "power-capped laptop" when showing latency.
- [ ] Docker Desktop running; `docker compose up -d postgres`; lab vLLM up
      (`HF_HOME_HOST=C:/Users/Dilip/.cache/huggingface docker compose --profile gpu up -d vllm`,
      ready after ~60 s: `curl localhost:8100/v1/models`).
- [ ] Four processes, each in its own terminal:
      `uv run poe api` (:8010), `uv run poe worker` (scans), `uv run poe runner` (Guard runs),
      `cd apps/web && pnpm dev --port 3100`. After editing API code, restart the API by hand:
      `--reload` waits for open live streams before it restarts.
- [ ] `uv run python scripts/rehearse.py` passes (about 2.5 minutes; it runs one real benchmark
      and one real Guard run, so the pages then show fresh results).
- [ ] `uv run furnace gh-check` prints the App and the `furnace-demo-f1` installation (needs the App).
- [ ] Demo repo has the R1 PR open and Guard has already run once on it (the local copy is ready at
      `C:\dev\furnace-demo-f1`: `main` = F1, branch `r1-request-id` = the R1 change; create the public
      repo, `git remote add origin ...`, `git push -u origin main r1-request-id`, open the PR).
- [ ] Browser tabs: landing, the F1 scan Blueprint, its graph, /lab, /guard/r1_dynamic_head,
      /bench, the demo repo's PR and the repair draft PR.
- [ ] Fallback: `docs/demo-shots/` (desktop), `docs/demo-shots/mobile/` (390 px) and the two
      rehearsal folders; regenerate with `uv run python scripts/demo_shots.py --base http://localhost:3100 --scan <id>`.

## Script

1. **(0:00) Problem.** "You already built the AI app. Nobody can tell you whether the next PR
   makes it slower or wrong." The landing hero replays one PR: main 232 ms p95 TTFT, the R1 PR
   1,043 ms with the prefix-cache hit at 0%, Furnace's repair 276 ms at 94% (RQ5, median of 3
   repeats; ticks are the repeats). Press **Replay**; the source links are under it.
2. **(0:30) The furnace is on.** Scroll to "The lab endpoint, right now": vLLM's own counters
   and the GPU's power, clock and temperature, every second. Nothing on it is animated unless
   the system moved.
3. **(0:50) Scan.** Paste `github.com/<you>/furnace-demo-f1`; the scan log types in stage by
   stage with real timings (a few seconds). The Blueprint shows the vLLM + Qwen endpoint with
   evidence chips, the README-vs-code model contradiction, the approval gate on `create_ticket`,
   and the prefix-stability finding. "Scan log" replays the stage timings.
4. **(1:30) Graph.** Open "Graph →"; click the `POST /chat` workflow; the path traces hop by hop
   through the handler, the system prompt, the model, the endpoint and the vLLM flags.
5. **(1:50) Inference Lab** (`/lab`). Press **Run it now** first (about 30 s): each dot is one
   real request's TTFT landing on the chart, against the RQ4 ticks for prefix caching on (blue)
   and off (ember). While it runs: F1's fingerprint from 89 real traces, prefix-cache hit
   predicted 89.0% vs measured ~89%, caching off multiplies p95 TTFT several-fold at every
   concurrency. The finished run's table shows its own measured hit rate and GPU clock.
6. **(2:50) Forge.** The Forge draft PR on the demo repo: manifest table (file, reason, target,
   risk), extracted prompt (byte-identical), installed tests. *(Needs the GitHub App.)*
7. **(3:15) Guard.** Open the R1 PR: the Furnace Guard check fails, ran a subset with reasons
   for what it skipped, perf table shows p95 TTFT and prefix-cache hit collapsing. Then
   `/guard/r1_dynamic_head`: press **Run Guard on this PR** (about 85 s, so press it at step 5
   and come back) — the impact graph lights the changed prompt, then what it reaches; each check
   flips to its verdict with its time; hover a check to see the path that selected it.
8. **(4:00) Repair.** Same page, below: regression test written first (fails on the PR, passes on
   main), localized hunk, rule-based fix, sandbox validation, perf gate, full-suite audit, and
   the draft repair PR. "A human merges. Furnace never touches production."
9. **(4:30) Evidence** (`/bench`). RQ1 held-out recall including the misses (unseen SDKs), RQ3
   recall at the share of the suite executed, RQ5 verified repairs, the negative results. Close.

## If something fails live

| failure | fallback |
|---|---|
| lab vLLM down / GPU busy | the live panel switches to "lab offline · showing recorded run" (RQ4 telemetry, labeled with its file); /lab and /guard read stored results |
| Run it now refused (one run at a time, cool-down, rate limit) | the message says why; the last run stays on the chart |
| Guard run: "No Guard runner is online" | start `uv run poe runner`, or show the last run (it replays from stored events) |
| GitHub scan rate-limited | show the scan of the same repo done earlier (keep its URL) |
| Network down | local stack + screenshots in `docs/demo-shots/` |
