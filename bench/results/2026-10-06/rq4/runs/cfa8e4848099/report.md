# furnace-bench report `cfa8e4848099`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1235
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `af8e9f49e7` · 2026-10-07T00:32:49.379681+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 138.7 | 142.1 [140.6, 143.0] | 143.3 [141.5, 143.8] | 9.71 | 10.18 | 1145.2 [695.1, 1734.0] |
| 2 | 0 | 60/60 | 151.5 | 257.8 [154.9, 268.7] | 269.7 [200.5, 271.4] | 16.10 | 21.88 | 3223.0 [1836.8, 3794.6] |
| 4 | 0 | 60/60 | 163.7 | 292.5 [269.9, 404.9] | 443.7 [284.5, 507.2] | 21.62 | 37.00 | 4025.6 [2210.4, 4873.1] |
| 8 | 0 | 60/60 | 262.3 | 651.5 [403.4, 878.9] | 904.2 [630.3, 945.5] | 36.30 | 52.64 | 4935.0 [2309.2, 5808.9] |
| 16 | 0 | 60/60 | 317.0 | 1567.7 [1122.9, 1770.3] | 1786.3 [1514.8, 1812.5] | 54.06 | 79.35 | 4436.3 [3201.0, 6043.6] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.12 | 74.6 | 2046.8 | 2.12 | 100.0 | 0.0 | – | 1.0% | 86.9% | 1.04 |
| 2 | 0 | 2.09 | 101.7 | 2050.3 | 2.09 | 100.0 | 0.0 | – | 2.0% | 89.7% | 1.03 |
| 4 | 0 | 3.04 | 149.8 | 2968.5 | 2.99 | 98.3 | 0.0 | – | 3.7% | 91.1% | 1.03 |
| 8 | 0 | 4.87 | 178.3 | 4740.2 | 4.46 | 91.7 | 0.0 | – | 6.8% | 93.4% | 1.04 |
| 16 | 0 | 5.72 | 219.7 | 5572.9 | 4.20 | 73.3 | 0.0 | – | 13.4% | 93.0% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-32 repeat=1

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
