# furnace-bench report `7e269d3354b5`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:04:28.579781+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 36.3 | 52.1 [48.9, 53.4] | 53.8 [51.2, 54.4] | 9.89 | 10.28 | 2126.9 [957.6, 2343.6] |
| 2 | 0 | 60/60 | 48.2 | 63.3 [59.7, 66.2] | 68.9 [62.9, 73.3] | 14.43 | 15.13 | 1818.6 [901.2, 2682.0] |
| 4 | 0 | 60/60 | 62.1 | 94.4 [83.8, 95.4] | 95.1 [89.4, 95.4] | 16.14 | 17.23 | 1854.9 [1000.4, 2262.3] |
| 8 | 0 | 60/60 | 76.5 | 158.8 [110.4, 160.0] | 159.6 [157.9, 160.0] | 18.60 | 21.60 | 2362.9 [1807.7, 2620.8] |
| 16 | 0 | 60/60 | 112.9 | 310.4 [221.6, 310.7] | 310.7 [258.7, 310.8] | 24.63 | 30.41 | 4291.9 [2915.0, 4548.4] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.85 | 95.4 | 1801.9 | 1.85 | 100.0 | 0.0 | 88.5% | 1.0% | 82.8% | 1.04 |
| 2 | 0 | 3.29 | 129.4 | 3203.2 | 3.29 | 100.0 | 0.0 | 88.9% | 1.1% | 88.5% | 1.05 |
| 4 | 0 | 6.11 | 217.5 | 5930.2 | 6.11 | 100.0 | 0.0 | 89.1% | 1.4% | 89.3% | 1.05 |
| 8 | 0 | 7.66 | 324.6 | 7421.2 | 7.66 | 100.0 | 0.0 | 89.2% | 1.8% | 88.5% | 1.04 |
| 16 | 0 | 8.51 | 444.2 | 8281.2 | 8.51 | 100.0 | 0.0 | 88.8% | 2.9% | 89.4% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-32 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
