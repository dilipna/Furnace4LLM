# Inference Lab optimizer (quality-constrained config selection)

Status: **design fixed before any grid was measured** (this file's commit precedes the first
`bench/results/*/optimizer/` result). Code: `packages/furnace/src/furnace/optimizer.py`
(decides, unit-tested) and `bench/optimize.py` (measures).

## Problem

From the plan (§7E): pick a serving configuration that maximizes goodput per cost subject to
quality not falling below the current configuration's by more than a tolerance, a failure
ceiling and the latency SLO. On one self-hosted GPU with no $/GPU-hour configured, cost is
"N/A" and the objective is SLO goodput, as the plan specifies.

## Grid (8 configs)

| knob | values | why |
|---|---|---|
| model | Qwen2.5-0.5B-Instruct (fp16), Qwen2.5-1.5B-Instruct-AWQ | the two models already served on this 4 GB GPU (2026-10-04); the only knob here that can change answer quality |
| prefix caching | on, off | the RQ4 effect |
| max-num-seqs | 8, 32 | the scheduler knob; 128 adds nothing at concurrency 8 |

Fixed: vLLM image pinned by digest (0.30.0), `--gpu-memory-utilization 0.70`,
`--max-model-len 4096`. **Baseline** = the compose default: 0.5B, prefix caching on,
max-num-seqs 32. Each config is a fresh container.

## Measurements per config

- **Quality.** The F1 app's own prompts for its 34 documented questions, rendered inside the
  sandbox from F1's code (retriever, context budget, system prompt), answered with the app's
  generation settings (max_tokens 256, temperature 0.2) under seeds 0, 1, 2. Two
  deterministic scores per question (share of the 3 seeds that pass):
  - `facts`: every number in the documented answer appears as a whole number in the answer
    (21 questions have a number; the other 13 are not scored on this metric);
  - `citations`: Furnace's `citation_required` check against the doc ids actually in the
    context (34 questions).
  A failed request counts as a failed answer.
- **Performance.** furnace-bench on workload W1 (the F1 trace fingerprint), closed loop at
  concurrency 8, 120 requests after 8 warmup, 3 consecutive runs: SLO goodput (TTFT p95 ≤
  500 ms), p95 TTFT, failure rate; SM clock recorded.

## Decision rules

- **Quality constraint**, per metric: the difference to the baseline is the mean of
  per-question differences (the question is the unit; seeds within a question are not
  independent samples), with a two-sided 90% t interval. Feasible only if the lower bound is
  ≥ −5 percentage points for every metric. "Not shown within tolerance" is infeasible, and
  reported separately from "worse than tolerance" (upper bound below −5).
- **Failures** ≤ 1% (median across runs). **p95 TTFT** ≤ 500 ms (median across runs).
- **Choice:** the feasible config with the highest median goodput. Feasible configs whose
  goodput min-max range overlaps the winner's are reported as indistinguishable; if the
  baseline is among them, the recommendation is to keep the baseline.
- **Pareto front** (goodput, p95 TTFT, each quality mean) is reported for every measured config.

## What this does not establish

One GPU and clock, one workload, one concurrency. Quality is two deterministic checks
(documented numbers, citation validity), not judged answer quality: the 2026-10-04 notes
record 1.5B-AWQ inventing a plan and contradicting a safety rule, which neither check sees.
The three performance runs per config are consecutive on one container, not interleaved
across configs, so slow drift between configs is not controlled. A pick is a recommendation
for this app on this machine, not a general result.

## Independent confirmation (added 2026-10-13, before any grid result exists)

The grid's selection is one measurement per config: three consecutive runs on one
container. Before any pick is reported as an improvement, it is rerun independently:

- **What is compared.** The baseline (A) against the selected config (B). If the selection
  keeps the baseline, B is the feasible config with the next highest median goodput, so
  "no change" is tested as well. If nothing is feasible, there is nothing to confirm.
- **How.** Eight fresh container launches, alternating A B B A A B B A (counterbalanced
  against slow drift); one performance run per launch (W1, c=8, 120 requests after 8
  warmup, seed 5000 + launch index; the grid used seeds 1234-1236); quality once per side
  on seeds 10, 11, 12 (the grid used 0, 1, 2). The launch is the unit, so launch-to-launch
  variation is part of the interval.
- **Decision** (`furnace.optimizer.confirm`; policy unchanged: 90% two-sided intervals,
  5-point quality tolerance, failures <= 1%, p95 TTFT <= 500 ms):
  - *confirmed*: the 90% Welch interval of B/A SLO goodput (log scale) lies above 0, and B
    meets the quality rule (paired by question) and the failure and SLO limits;
  - *not confirmed: no improvement*: the interval's upper bound is at or below 0;
  - *not confirmed: constraints*: goodput higher, but quality, failures or SLO not shown;
  - *inconclusive*: the interval contains 0 (or a run had zero goodput).
  The grid's own result is reported as it is either way; the confirmation decides only
  whether a change is recommended as an improvement.
