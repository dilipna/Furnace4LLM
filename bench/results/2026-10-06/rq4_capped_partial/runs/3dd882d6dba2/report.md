# furnace-bench report `3dd882d6dba2`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `03c6b6279b` · 2026-10-06T03:39:40.442861+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 138.9 | 141.8 [140.8, 145.3] | 161.6 [141.6, 188.5] | 9.65 | 10.21 | 2189.6 [1083.0, 2440.7] |
| 2 | 0 | 60/60 | 153.6 | 260.2 [157.2, 276.8] | 277.0 [160.7, 277.2] | 15.50 | 21.58 | 2476.3 [1229.1, 3331.3] |
| 4 | 0 | 60/60 | 166.0 | 401.6 [274.0, 413.9] | 453.5 [332.5, 518.3] | 24.13 | 33.64 | 2920.0 [1638.7, 3342.9] |
| 8 | 0 | 60/60 | 180.5 | 658.3 [400.2, 885.8] | 920.0 [605.3, 976.2] | 34.12 | 53.78 | 4223.9 [3197.0, 5384.9] |
| 16 | 0 | 60/60 | 1861.5 | 2367.1 [2197.0, 2430.7] | 2460.0 [2347.5, 2507.9] | 30.11 | 47.99 | 7528.8 [5379.4, 8661.2] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.58 | 81.4 | 1538.3 | 1.58 | 100.0 | 0.0 | – | 1.2% | 87.0% | 1.04 |
| 2 | 0 | 2.42 | 95.1 | 2353.7 | 2.42 | 100.0 | 0.0 | – | 2.1% | 90.2% | 1.05 |
| 4 | 0 | 3.77 | 133.9 | 3652.3 | 3.70 | 98.3 | 0.0 | – | 4.1% | 91.8% | 1.05 |
| 8 | 0 | 4.35 | 184.2 | 4210.9 | 3.98 | 91.7 | 0.0 | – | 7.8% | 92.9% | 1.04 |
| 16 | 0 | 4.00 | 208.9 | 3893.5 | 0.20 | 5.0 | 0.0 | – | 8.1% | 92.6% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-8 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
