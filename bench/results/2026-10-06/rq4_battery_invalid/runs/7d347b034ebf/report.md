# furnace-bench report `7d347b034ebf`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `979350bef2` · 2026-10-06T02:41:32.179594+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 44.0 | 59.0 [56.9, 61.2] | 62.1 [57.9, 63.5] | 11.08 | 12.12 | 2429.6 [1098.2, 2564.9] |
| 2 | 0 | 60/60 | 55.4 | 73.2 [67.0, 75.4] | 76.7 [70.8, 78.7] | 16.20 | 16.96 | 1965.3 [1005.1, 2965.9] |
| 4 | 0 | 60/60 | 68.7 | 99.2 [82.7, 106.6] | 106.8 [92.8, 107.0] | 17.72 | 18.89 | 2072.8 [1109.2, 2476.6] |
| 8 | 0 | 60/60 | 86.0 | 182.3 [118.2, 183.3] | 183.3 [182.0, 183.4] | 20.55 | 23.59 | 2620.8 [2078.7, 2979.2] |
| 16 | 0 | 60/60 | 125.8 | 371.2 [288.3, 371.5] | 371.9 [323.1, 372.4] | 26.96 | 32.75 | 4813.0 [3215.9, 5114.5] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.64 | 84.5 | 1596.3 | 1.64 | 100.0 | 0.0 | 88.5% | 1.4% | 75.6% | 1.04 |
| 2 | 0 | 2.94 | 115.7 | 2864.0 | 2.94 | 100.0 | 0.0 | 88.7% | 1.6% | 81.0% | 1.05 |
| 4 | 0 | 5.58 | 198.4 | 5409.3 | 5.58 | 100.0 | 0.0 | 89.1% | 2.0% | 80.3% | 1.05 |
| 8 | 0 | 6.87 | 291.2 | 6657.4 | 6.87 | 100.0 | 0.0 | 89.2% | 2.6% | 81.5% | 1.04 |
| 16 | 0 | 7.51 | 392.0 | 7307.1 | 7.51 | 100.0 | 0.0 | 88.8% | 4.2% | 80.8% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-128 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
