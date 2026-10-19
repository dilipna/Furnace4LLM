# Prefix cache and prompt layout: frozen protocol

Protocol date: 2026-10-19. Frozen before measuring this experiment. Synthetic operations
runbook, Qwen2.5-0.5B-Instruct on the existing 4 GB laptop GPU. This is the smaller-model
revision agreed in chat, not the original proposed Qwen3-4B experiment.

Question: how do prefix caching and placement of volatile request metadata affect streamed
TTFT on this workload? No latency difference or successful mitigation is assumed.

| Condition | Prefix caching | System message |
|---|---|---|
| A | on | Byte-identical shared runbook |
| B | off | Same runbook and queries as A |
| C | on | Unique session UUID and timestamp before the runbook |
| D | on | The same per-request metadata after the runbook |

Three repeats, each with a fresh server for each condition. Rotate order: ABCD, BCDA,
CDAB. Four distinct warmup requests, excluded, then 60 measured requests at concurrency
one. The same 60 varied queries and deterministic order are used across conditions.
The runbook is trimmed to 1450–1500 tokens using the served tokenizer; actual length and
SHA-256 are saved. C/D metadata are paired by query and repeat. All outputs are fixed at
32 tokens (ignore EOS) to control decode length; this is a serving benchmark, not a test
of answer quality. Context limit 4096, GPU allocation 0.70, maximum sequences 8, block size
16, server seed 7. Only the cache toggle varies among server launch flags.

Use the existing `furnace_bench.runner.run_benchmark`, streaming client and adapter;
TTFT is send to the first generated-output chunk, excluding empty/role-only chunks.
Record first-byte timing separately in raw request records. Count output tokens from
server usage only, never substitute stream chunks for tokens in the published throughput.

Save each run's p50/p95, server-reported completion tokens divided by its measured window,
failures, and cache-counter deltas. Report cache hit percentages emitted in server logs
as logged observations, with their interval/cumulative limitation; do not silently substitute
Prometheus data for missing log statistics. Save metrics before/after separately.

The main table reports the median of the three run-level p50s, p95s and throughputs, plus
the measured-window cache ratio from summed counter deltas. Show every run separately.
The chart shows medians and min–max across runs, not confidence intervals. Three runs
are insufficient to claim a reliable population tail-latency estimate. The 180 requests
per condition are not 180 independent experimental repeats.

Poll /v1/models for readiness. Startup failure or any failed measured request invalidates
that attempt; preserve it and retry once with identical settings. Never populate a result
from a missing/failed run. Do not change memory flags, model, workload, or sample count
mid-campaign. Stop if the unchanged configuration cannot run.

Record GPU/driver, AC state, model revision, image digest, exact flags, protocol/workload
hashes, run order, and per-run GPU observations. Limit claims to this model, workload,
concurrency, output length and hardware. No inference about customer adoption, production
incidents prevented, dollars saved, or behavior of a 4B model follows from this experiment.

Publication is manual: do not commit or push from the experiment script.

## Input validation correction, before any measured request

The initial campaign `2026-10-19-small-model` found only 1281 tokens in the runbook source
and stopped before warmup or measurement. Its identical automatic retry was interrupted
during server startup to correct the input; the temporary container was removed. The
runbook source was extended with routing, capacity planning and configuration sections.
The 1450–1500-token target, model, serving flags, conditions and request counts are unchanged.
The corrected campaign has its own directory and hashes. The failed premeasurement attempt
is retained and is not a performance observation or a successful trial.
