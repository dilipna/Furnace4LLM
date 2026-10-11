# Case study: making an LLM app faster without breaking it, and proving it

Furnace is an inference-reliability retrofit for existing Python LLM applications. It reads a
repository, installs justified evals and benchmarks as a draft PR (Forge), and on every later
pull request runs only the checks the diff can affect (Guard); when a PR causes a
performance regression it can explain, it writes a failing test first and proposes a
verified repair as another draft PR. A human always merges. Everything below was measured
on a laptop RTX 3050 Ti (4 GB) serving Qwen2.5-0.5B-Instruct with vLLM; every number links
to a file in `bench/results/`.

## What is deterministic and what is not

| part | how | model-powered? |
|---|---|---|
| Scan (call sites, prompts, routes, graph, findings) | Python AST + config/doc parsing, noisy-OR reconciliation | no |
| Forge (harness, prompt extraction, tests, CI) | templates and codemods, sandbox-validated | no |
| Guard impact analysis | graph diff between base and head | no |
| Perf gate | load generation + bootstrap statistics | no (measures the served model) |
| Repair | rule strategies over the AST, gated by tests and the perf gate | no |
| Quality checks | deterministic checks; LLM judge built, not calibrated (no key) | judge only |

## Hard problem 1: a regression you can measure, on hardware that lies

The motivating bug (R1): a developer adds a request id and timestamp to the top of the system
prompt "for debugging". Functionally nothing changes. With vLLM's automatic prefix caching,
every request now has a unique first token, so no KV-cache block is ever reused: on F1's
workload p95 TTFT rose by **+905% to +1,004%** and the prefix-cache hit rate fell from 98%
to 0% (`2026-10-09-gate-warmup-v2/rq5.md`).

Measuring that is easy; measuring that a *fix* is fine is not. Three findings shaped the gate:

1. **The instrument was biased.** An A/A test (a revision against itself) found differences
   up to 60%: the first wave after the GPU idled took ~200 ms instead of ~65 ms and set the
   p95, and the base revision was always measured first. A published RQ5 result was
   withdrawn in a dated correction; an unmeasured warmup wave fixed the bias
   (`2026-10-06/CORRECTIONS.md`, `2026-10-09/gate_noise*.md`).
2. **The noise bound was optimistic.** The post-fix A/A gave "within 9.7%" from 12 trials.
   A second A/A on 2026-10-11, same clock, found +13.4% and +13.0% between identical
   revisions: the old point rule would have raised 2/12 false WARNs
   (`2026-10-11-gate-ci/gate_noise.md`).
3. **p95 from 34 requests is nearly the maximum.** So the gate now decides on a 95%
   hierarchical-bootstrap interval (runs, then requests within runs), rotates run order,
   keeps raw per-request data, and has an honest fourth verdict, INCONCLUSIVE. On the same
   12 A/A trials: 0 false WARN or BLOCK, 7 PASS, 5 INCONCLUSIVE, and the interval contained
   the true difference (0) in 12/12. PENDING_X4

Alternatives considered: fixed thresholds on the point estimate (what failed above); more
repeats only (helps, costs GPU minutes per PR); a Mann-Whitney test on per-request TTFT
(ignores between-run variance, which dominates here). The interval is coarse at this sample
size and says so instead of passing.

## Hard problem 2: repairs that do not create a new regression

The repair loop is bounded on purpose: no free-form LLM edits. It writes the regression test
first and refuses to continue unless the test fails on the PR head and passes on the base,
localizes the hunk through the graph, and tries deterministic strategies in order. The first
strategy (keep the request id, move it to the end of the last user message) is functionally
correct but was still +40% to +50% slower than main, and the perf gate rejected it before the
second strategy (log the value instead of sending it) was accepted
(`2026-10-09-gate-warmup-v2/`). The acceptance rule is now interval-based: the candidate must
be faster than the PR head with 95% confidence and its worst case against main must stay
below the block threshold. PENDING_RQ5

## Hard problem 3: side effects exactly once

A retried job used to open a second pull request (the branch name took a `-2` suffix), and a
redelivered webhook enqueued a second Guard run. Fixes, each with a test: draft PRs are
idempotent by content (Git trees are content-addressed, so the same change on the same base
returns the existing PR, open or closed, and never overwrites a branch); every delivery GUID
is recorded once; one active Guard job per PR head commit; check runs reused per commit and
scoped to this App; job writes fenced by (worker, attempt) so a stalled worker cannot
overwrite the claim that replaced it, and a lost lease cancels the handler; errors scrubbed
of credentials before they become job events or check text.

## Hard problem 4: not overfitting to one demo app

Scanner changes are measured on held-out apps labeled and committed before any scan. On
held-out set 3 (Gemini, Mistral, Replicate, Bedrock, Cohere apps) LLM call-site recall went
from 1/9 to 8/9 at precision 1.00 (`2026-10-09/rq1.md`). Set 4 (three apps chosen on
2026-10-11, labels committed in `f0fce9d` before any scan) tests what a demo hides: an app
whose calls all go through the OpenAI Agents SDK, a Redis-backed tool-calling chatbot, and a
minimal Responses-API backend. PENDING_SET4

## A measurement mistake caught

The Kernel Lab first showed a Triton RMSNorm kernel 9x faster than `torch.compile`. The
compiled baseline had silently fallen back to eager after 8 recompilations; compiling each
shape fresh put the two at parity (both ~9.8x eager, 99% of measured copy bandwidth,
36/36 correct; `kernel_lab/results/2026-10-09/`).

## Limitations

- One GPU, one small model, one workload family; latency depends on the clock the driver
  picks (780 MHz vs ~1,960 MHz across reboots), so comparisons are made only at equal clocks.
- Only one regression signature is repairable (prefix instability).
- The GitHub App path is tested against a mock GitHub; the live run needs the App
  (`docs/github-app.md`). PENDING_LIVE
- Labels were written by the developer agent and not independently reviewed.
- Python only; LLM-judge calibration needs human labels and a key.
