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
| Perf gate | load generation + run-level interval statistics | no (measures the served model) |
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
3. **p95 from 34 requests is nearly the maximum.** The gate then moved to a 95%
   hierarchical-bootstrap interval with an honest fourth verdict, INCONCLUSIVE (12 A/A
   trials: 0 false WARN or BLOCK, 5 INCONCLUSIVE). With 5 runs per side it was still
   INCONCLUSIVE in 7/8 A/A trials: more runs did not help.
4. **The statistic, not the run count, was the limit.** Requests in a closed-loop run arrive
   in waves that share a scheduler step (62% of consecutive TTFTs within 3%), so 34 requests
   behave like about 4-5 independent observations, and the request-level bootstrap treated them as 34.
   On the 20 earlier A/A trials (and only those), every candidate was compared: pooling all
   requests is the worst choice for a tail (one slow run sets the pooled p95; A/A spread
   0.167 on the log scale), while a run's geometric-mean TTFT has half the run-to-run noise
   of its p95. The revision, frozen in `docs/gate-revision.md` before any code changed:
   geometric-mean TTFT, the run as the unit, a 90% Welch t interval, the plan's unchanged
   10% / 25% thresholds; p95 is reported but does not decide. What it gives up is stated: a
   regression confined to the slowest few percent of requests is not seen. On the
   development data it gives PASS 87% / INCONCLUSIVE 13% (optimistic: chosen there); a fresh
   validation (unchanged code, a restored baseline, regressions of about +13%, +18%, +30%
   and +800%) is in progress in `2026-10-12-gate-validation/`: 14 of 24 unchanged-code
   trials so far, 0 false FAIL, 10 PASS, 4 INCONCLUSIVE.

Alternatives rejected on data: fixed thresholds on the point estimate (false WARNs above);
more requests per run (adds waves slowly, does nothing about run-to-run variation); pooled
p95 (worst of all); a Mann-Whitney test on per-request TTFT (treats dependent requests as
independent).

## Hard problem 2: repairs that do not create a new regression

The repair loop is bounded on purpose: no free-form LLM edits. It writes the regression test
first and refuses to continue unless the test fails on the PR head and passes on the base,
localizes the hunk through the graph, and tries deterministic strategies in order. The first
strategy (keep the request id, move it to the end of the last user message) is functionally
correct but was still +40% to +50% slower than main, and the perf gate rejected it before the
second strategy (log the value instead of sending it) was accepted
(`2026-10-09-gate-warmup-v2/`). The acceptance rule is now interval-based: the candidate must
be faster than the PR head with 95% confidence and its worst case against main must stay
below the block threshold. That rule is strictly stronger than the point rule RQ5 first
used, and re-measured on 2026-10-12 it verified **1/3**: the good candidate (+1.7% to +8.6%
vs main, prefix-cache hit back to 98%) was refused twice because its interval reached
+30% and +33%. No unproven repair was accepted, but at 3 runs x 34 requests the gate rarely
has the power to confirm a good one; an A/A run with 5 runs per side did not narrow the
interval (7/8 INCONCLUSIVE), so the decision statistic (a median of per-run p95s), not the
run count, was the limit (`2026-10-12-gate-ci/NOTES.md`). The gate has since been revised
(hard problem 1, point 4); repair under the revised gate is queued and **not measured yet**,
and its result will be reported whatever it is: the thresholds were not changed to let it pass.

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
from 1/9 to 8/9 with no false positive (8 of 8 predicted; `2026-10-09/rq1.md`); set 3
was used to make that change, so 8/9 is not a held-out figure. Set 4 (three apps chosen on
2026-10-11, labels committed in `f0fce9d` before any scan) tests what a demo hides: an app
whose calls all go through the OpenAI Agents SDK, a Redis-backed tool-calling chatbot, and a
minimal Responses-API backend. First scan: **2/9 LLM call sites** (2 predicted, both right); the
Agents SDK calls, a client held in a dict and env/settings model defaults are not resolved.
What held up is failing safe: the 10 evidence items behind its 11 findings point at
existing files and line ranges that contain their excerpts (a consistency check of the
links, not of whether a finding is right; no label set measures that); docs-only and unrelated-code PRs selected no checks (6/6); an injected prompt
regression was caught by the prefix check in 2 of 3 apps, but the perf gate was not reached
in any (0/3 fully correct); Forge planned on 1 of 3 and refused with a stated reason on the
others. Validating Forge there exposed a real infrastructure gap: the sandbox installed only
a root `requirements.txt`. It now installs the project's `requirements-dev.txt` with
in-repository includes (escapes refused), and one app's own suite runs in the sandbox (5
passed, 1 pre-existing failure, so Forge still correctly opens no PR). Set 4 is no longer
held-out for anything changed after that first scan (`2026-10-11-external/NOTES.md`).

The fixes were then measured the right way: a fifth set (`openai/openai-cs-agents-demo`) was
labeled and committed before the scanner change, and went from 0/3 to 3/3 call sites (3
predicted, all right), while F1 and sets 1-3 stayed identical in every category. One app is
evidence the change generalizes, not a recall estimate. With agent instructions analyzed as
system prompts, Guard picks the right checks on all 9 synthetic set-4 PRs; repair still
does not rewrite agent instructions, and says so.

Pooled over all five held-out sets, on each set's first scan: **4/34 call sites found**
(12%; 95% CI 5-27%), 4 of 4 predictions right. After the fixes each set prompted, the same
34 labels score 33/34, which measures fit to those apps, not generalization
(`2026-10-12-reconcile/scanner_reconciliation.md`).

## A measurement mistake caught

The Kernel Lab first showed a Triton RMSNorm kernel 9x faster than `torch.compile`. The
compiled baseline had silently fallen back to eager after 8 recompilations; compiling each
shape fresh put the two at parity (both ~9.8x eager, 99% of measured copy bandwidth,
36/36 correct; `kernel_lab/results/2026-10-09/`).

## Limitations

- One GPU, one small model, one workload family; latency depends on the clock the driver
  picks (780 MHz vs ~1,960 MHz across reboots), so comparisons are made only at equal clocks.
- Only one regression signature is repairable (prefix instability).
- The GitHub App path (Forge PR, check run, repair PR, webhooks) is tested against a mock
  GitHub only; the live run needs the App (`furnace gh-setup`, two clicks) and has not been
  done. Until it is, "works on real GitHub" is not claimed.
- Scanner recall drops on indirection it does not model yet (routes reaching calls through
  framework servers or background tasks, env/settings model defaults: models 0/6 on set 4).
- Labels were written by the developer agent and not independently reviewed.
- Python only; LLM-judge calibration needs human labels and a key.
