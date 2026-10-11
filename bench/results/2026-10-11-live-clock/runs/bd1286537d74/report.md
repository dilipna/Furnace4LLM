# furnace-bench report `bd1286537d74`

- **Target:** `vllm` · model `lab` · http://localhost:8100/v1 · lab vLLM
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 20 req/level (+2 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 89152
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `59ab0eafba` · 2026-10-11T03:25:52.014219+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 20/20 | 23.9 | 30.6 [26.8, 32.0] | 31.7 [28.7, 32.0] | 7.73 | 8.09 | 778.0 [325.3, 1004.4] |
| 2 | 0 | 20/20 | 32.7 | 44.9 [41.1, 46.1] | 45.9 [41.7, 46.1] | 8.48 | 8.74 | 1387.0 [566.5, 1738.6] |
| 4 | 0 | 20/20 | 38.8 | 55.4 [47.4, 55.7] | 55.7 [52.1, 55.7] | 8.80 | 9.71 | 2083.1 [593.2, 2352.3] |
| 8 | 0 | 20/20 | 46.1 | 91.2 [90.4, 94.8] | 94.1 [90.6, 94.8] | 10.76 | 11.57 | 1179.3 [443.5, 2075.0] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 3.50 | 120.4 | 3320.1 | 3.50 | 100.0 | 0.0 | 91.2% | 0.8% | 77.8% | 1.06 |
| 2 | 0 | 4.39 | 216.1 | 4240.0 | 4.39 | 100.0 | 0.0 | 89.3% | 0.9% | 78.4% | 1.03 |
| 4 | 0 | 6.87 | 390.1 | 6702.4 | 6.87 | 100.0 | 0.0 | 88.6% | 1.3% | 80.7% | 1.03 |
| 8 | 0 | 8.62 | 343.8 | 8369.2 | 8.62 | 100.0 | 0.0 | 89.0% | 1.4% | 80.6% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
