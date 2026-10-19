# Furnace: an engineering review in five minutes

Furnace is a Python LLM application's pre-merge inference-performance check. Its narrow
question is: did this code or prompt change make serving slower on the same endpoint?
The standalone prefix-cache experiment below isolates one reason that can happen.
No accounts, GPU or API key are needed to inspect its saved evidence.

## Start with one concrete result

In a controlled Qwen2.5-0.5B workload on an RTX 3050 Ti 4 GB, moving the same unique
session metadata from before a shared 1500-token runbook to after it recorded 234.45 ms
versus 43.27 ms median run p50 TTFT, an 81.5% reduction. Cached-token reuse changed from
0% to 94%. The result covers four conditions, three fresh-server repeats per condition,
and 60 measured requests per run. It is not a production speed guarantee.

Read the [one-page method and limits](../experiments/prefix-cache/writeup.md), open the
[portable report](../experiments/prefix-cache/review.html), or inspect
[every attempt and raw record](../experiments/prefix-cache/results.md).

## Verify it from a clone

```bash
# Python 3.12, standard library only; no inference or network calls.
python experiments/prefix-cache/review.py

# Optional: regenerate the self-contained report after checking the evidence.
python experiments/prefix-cache/review.py --html experiments/prefix-cache/review.html
```

Expected: 12 successful runs, 720 measured requests, all consistency checks true, exit 0.
Missing artifacts, changed raw timings, changed cache snapshots, or a stale published
table cause a nonzero exit. This checks internal consistency; an author could fabricate
an internally consistent dataset, so it is not independent authentication of a run.

Then connect the serving result to the product's existing generated test:

```bash
python experiments/prefix-cache/rehearse_guard.py
```

Expected: A/B/D pass and C fails in each repeat. The script runs the literal Forge test
against saved messages, without importing an application or calling a model. Its B
control passes despite disabled caching: a structural prefix check cannot replace the
latency gate. The [walkthrough](../experiments/prefix-cache/guard-demo.md) also documents
how to use the command on your own base/head rendered snapshots with CI exit codes.

## Inspect the engineering choices

| Question | Implementation / evidence | Why it matters |
|---|---|---|
| What exactly is timed? | Existing [FurnaceBench streaming client](../packages/inference/src/furnace_bench/client.py); [experiment driver](../experiments/prefix-cache/benchmark.py) | Reuses the serving harness; excludes role-only chunks from first generated output. |
| Is the comparison controlled? | [Frozen protocol](../experiments/prefix-cache/protocol.md) and [manifest](../experiments/prefix-cache/runs/2026-10-19-small-model-v2/manifest.json) | Same model/image/flags, paired queries and metadata, rotated condition order; caching toggle differs. |
| Are headline values auditable? | [Verifier](../experiments/prefix-cache/verify.py) and [publication audit](../experiments/prefix-cache/review.py) | Recomputes request percentiles/throughput and cache-token counters, then checks the published numbers. |
| Does it reject corrupted evidence? | [Corruption tests](../experiments/prefix-cache/test_review.py) and [protocol tests](../experiments/prefix-cache/test_protocol.py) | Tests deliberately alter temporary copies; recorded measurements remain unchanged. |
| Are failures hidden? | All attempts in [results](../experiments/prefix-cache/results.md); all run statistics in the report | Failed startup and the 3072.90 ms cache-off p95 remain visible. |
| How does this connect to a PR check? | [Gate design](gate-revision.md), [validation](../bench/results/2026-10-12-gate-validation/validation/report.md), [real GitHub run](../bench/results/2026-10-14-live-github/verify.md) | Links the isolated mechanism to the existing regression gate without pooling different experiments. |

## Boundaries worth discussing

- **Latency location versus tails:** the gate decides on run-level geometric-mean TTFT
  and a 90% interval. The prefix experiment reports medians of run p50/p95 statistics.
  These are distinct analysis units; neither result proves a production tail SLO.
- **Noise versus false confidence:** three repeats expose variability but provide limited
  power. Existing gate validation left many small regressions inconclusive. An inconclusive
  outcome must stay distinct from a pass.
- **Cache efficiency versus application meaning:** moving metadata preserves the text but
  may change its salience to a model. No answer-quality evaluation was run here; production
  adoption requires that check and a representative concurrency/length workload.
- **Usability versus infrastructure:** inspecting results needs only Python. Repeating the
  GPU experiment requires the pinned cached model/image and the documented Docker/GPU setup.
- **Scope versus adoption:** the hosted product is a recorded demonstration. There is no
  claimed customer deployment, multi-tenant production service or external endorsement.

## Next evidence that would change confidence

A representative external application's workload, an independently rerun campaign,
longer outputs and a concurrency sweep would test transfer beyond this laptop. Those
results do not exist in this experiment. More interface features would not supply them.
