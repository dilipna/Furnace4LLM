# Prompt metadata placement and vLLM prefix-cache reuse

**Measured on October 19, 2026.** Moving per-request metadata behind a shared runbook
recorded **43.27 ms versus 234.45 ms median run p50 TTFT** (81.5% lower)
and restored **94.00% cached-token reuse** in this synthetic workload.

## Problem

Enabling prefix caching does not ensure that an application presents reusable prefixes.
vLLM's cache keys incorporate preceding blocks, so unique fields at the beginning can
prevent reuse of otherwise identical text. This is expected behavior, documented in
[vLLM's cache design](https://docs.vllm.ai/en/latest/design/prefix_caching/).
This experiment quantifies that prompt-layout effect; it makes no novelty claim.

## Method

Qwen2.5-0.5B-Instruct, revision `7ae557604adf67be50417f59c2c2f167def9a775`, vLLM 0.30.0,
RTX 3050 Ti Laptop GPU (4096 MiB), driver 592.82, Docker/WSL2, AC power. The shared
system runbook is exactly 1500 tokens. Each condition has 60 varied queries, four excluded
warmups and three fresh-server repeats, rotated in order: ABCD, BCDA, CDAB. Concurrency
one, temperature zero, fixed 32-token completions with ignore-EOS. C and D use identical
per-query UUID/timestamp metadata; its placement changes. Same server flags throughout:

```text
--model Qwen/Qwen2.5-0.5B-Instruct --revision 7ae557604adf67be50417f59c2c2f167def9a775 --served-model-name lab --gpu-memory-utilization 0.70 --max-model-len 4096 --max-num-seqs 8 --block-size 16 --seed 7
```

Add `--enable-prefix-caching` for A/C/D or `--no-enable-prefix-caching` for B.
The immutable image digest is in the [manifest](runs/2026-10-19-small-model-v2/manifest.json).
FurnaceBench's existing streaming client measures send to the first generated-output
chunk, excluding role-only chunks. No timing implementation was duplicated.

## Results

| Condition | TTFT p50 (ms) | TTFT p95 (ms) | Completion tok/s | Cache hit (metrics delta) |
|---|---:|---:|---:|---|
| A: Stable, cache on | 34.92 | 39.69 | 88.89 | 98.13% |
| B: Stable, cache off | 208.74 | 220.77 | 61.14 | N/A (disabled) |
| C: Metadata first | 234.45 | 246.39 | 56.61 | 0.00% |
| D: Metadata last | 43.27 | 49.20 | 86.27 | 94.00% |

TTFT and throughput entries are medians of three run statistics, not pooled-request
percentiles. Completion tok/s uses server-reported tokens over the measured wall-time
window. Cache reuse uses token-counter deltas; B has no cache queries. Log statistics were
visible and are [listed separately](results.md), including warmup traffic.

## Interpretation and limits

Caching alone did not preserve reuse when metadata came first. Moving it after the
runbook produced 5.42× lower median run p50 TTFT in this comparison. This is a
workload-specific observation, not a production speed guarantee. The main chart shows
both median comparisons and full observed run ranges: one cache-off trial had p95
3072.90 ms, versus 214.05 and 220.77 ms in the others. No outliers were removed.

Single GPU/model, synthetic independent queries, short fixed outputs, three repeats,
no concurrency sweep, no answer-quality evaluation. Laptop/WSL runtime behavior and
profiled KV allocation varied; this does not isolate pure cache-lookup overhead. It
establishes no Qwen3-4B result or customer impact. The original 4B plan was revised for
the available 4 GB GPU; a fourth condition tests a mitigation and three repeats expose
variation. No serving flags were changed between conditions except the caching toggle.

The initial runbook-length check failed before measurement and was corrected in the
[protocol addendum](protocol.md). One corrected-campaign startup failed with CUDA
device-busy/unavailable; its identical retry succeeded. Both records are retained.
All 720 measured requests succeeded. [Raw-data verification](verification.json) recomputes
percentiles and throughput and checks paired workloads. Reproduce with
`bash experiments/prefix-cache/run.sh my-campaign` from the repository root.
