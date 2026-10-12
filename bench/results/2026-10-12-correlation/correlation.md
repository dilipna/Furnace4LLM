# TTFT vs vLLM queue state (stored RQ4 runs)

Each successful request joined with the vLLM /metrics sample at its send time; Spearman's rho per concurrency level (levels are not pooled: concurrency drives both). Median across 3 repeats, range in parentheses. Descriptive: requests in a run are dependent, so no p-values. Source: `bench/results/2026-10-06/rq4/` (AC, 780-830 MHz).

| config | concurrency | requests | max waiting | rho(waiting, TTFT) | rho(running, TTFT) |
| --- | ---: | ---: | ---: | ---: | ---: |
| pc-off_seqs-128 | 1 | 180 | 0 | n/a (constant) | -0.10 (-0.15 to +0.04) |
| pc-off_seqs-128 | 2 | 180 | 0 | n/a (constant) | -0.20 (-0.24 to -0.06) |
| pc-off_seqs-128 | 4 | 180 | 0 | n/a (constant) | -0.05 (-0.23 to -0.00) |
| pc-off_seqs-128 | 8 | 180 | 0 | n/a (constant) | -0.39 (-0.40 to -0.21) |
| pc-off_seqs-128 | 16 | 180 | 0 | n/a (constant) | -0.61 (-0.71 to -0.60) |
| pc-off_seqs-32 | 1 | 180 | 0 | n/a (constant) | +0.04 (-0.01 to +0.14) |
| pc-off_seqs-32 | 2 | 180 | 0 | n/a (constant) | -0.12 (-0.20 to -0.10) |
| pc-off_seqs-32 | 4 | 180 | 0 | n/a (constant) | +0.01 (-0.07 to +0.09) |
| pc-off_seqs-32 | 8 | 180 | 0 | n/a (constant) | -0.41 (-0.47 to -0.32) |
| pc-off_seqs-32 | 16 | 180 | 0 | n/a (constant) | -0.62 (-0.64 to -0.58) |
| pc-off_seqs-8 | 1 | 180 | 0 | n/a (constant) | +0.04 (-0.03 to +0.14) |
| pc-off_seqs-8 | 2 | 180 | 0 | n/a (constant) | -0.12 (-0.19 to -0.07) |
| pc-off_seqs-8 | 4 | 180 | 0 | n/a (constant) | -0.17 (-0.21 to -0.06) |
| pc-off_seqs-8 | 8 | 180 | 0 | n/a (constant) | -0.46 (-0.48 to -0.30) |
| pc-off_seqs-8 | 16 | 180 | 8 | +0.06 (+0.04 to +0.41) | +0.21 (+0.09 to +0.44) |
| pc-on_seqs-128 | 1 | 180 | 0 | n/a (constant) | +0.06 (+0.03 to +0.07) |
| pc-on_seqs-128 | 2 | 180 | 0 | n/a (constant) | -0.18 (-0.26 to -0.17) |
| pc-on_seqs-128 | 4 | 180 | 0 | n/a (constant) | -0.26 (-0.29 to -0.20) |
| pc-on_seqs-128 | 8 | 180 | 0 | n/a (constant) | -0.37 (-0.43 to -0.37) |
| pc-on_seqs-128 | 16 | 180 | 0 | n/a (constant) | -0.58 (-0.60 to -0.53) |
| pc-on_seqs-32 | 1 | 180 | 0 | n/a (constant) | -0.11 (-0.20 to -0.05) |
| pc-on_seqs-32 | 2 | 180 | 0 | n/a (constant) | -0.15 (-0.18 to +0.18) |
| pc-on_seqs-32 | 4 | 180 | 0 | n/a (constant) | -0.21 (-0.27 to -0.20) |
| pc-on_seqs-32 | 8 | 180 | 0 | n/a (constant) | -0.29 (-0.47 to -0.27) |
| pc-on_seqs-32 | 16 | 180 | 0 | n/a (constant) | -0.60 (-0.67 to -0.55) |
| pc-on_seqs-8 | 1 | 180 | 0 | n/a (constant) | -0.06 (-0.11 to -0.01) |
| pc-on_seqs-8 | 2 | 180 | 0 | n/a (constant) | -0.10 (-0.19 to +0.02) |
| pc-on_seqs-8 | 4 | 180 | 0 | n/a (constant) | -0.24 (-0.36 to -0.16) |
| pc-on_seqs-8 | 8 | 180 | 0 | n/a (constant) | -0.39 (-0.39 to -0.36) |
| pc-on_seqs-8 | 16 | 180 | 8 | +0.41 (+0.22 to +0.60) | +0.35 (+0.21 to +0.54) |

n/a: the state was constant at that level (`waiting` stayed 0: vLLM queued nothing), so there is nothing to correlate. vLLM queues only when concurrency exceeds max-num-seqs.

Resolution limit: telemetry is sampled about every 0.3 s while TTFT is tens to hundreds of ms, so the state 'at send' is the last sample up to ~0.3 s earlier. The negative rho(running, TTFT) at c >= 8 is consistent with that staleness (a request sent just after a wave finished sees the earlier, higher count) and is not interpreted further.
