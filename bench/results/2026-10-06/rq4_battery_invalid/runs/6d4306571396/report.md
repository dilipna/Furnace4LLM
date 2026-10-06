# furnace-bench report `6d4306571396`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `979350bef2` · 2026-10-06T02:45:45.820234+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 148.6 | 155.4 [152.5, 157.5] | 157.6 [155.0, 157.6] | 11.09 | 11.85 | 2516.9 [1185.8, 2719.2] |
| 2 | 0 | 60/60 | 167.9 | 282.9 [182.7, 288.3] | 291.5 [271.3, 296.7] | 16.73 | 23.03 | 2550.6 [1320.1, 3635.7] |
| 4 | 0 | 60/60 | 173.7 | 420.8 [281.0, 438.3] | 472.5 [353.5, 528.5] | 26.04 | 36.53 | 3147.3 [1761.4, 3611.0] |
| 8 | 0 | 60/60 | 236.6 | 719.4 [412.9, 932.0] | 966.3 [640.0, 1022.4] | 36.80 | 56.50 | 4576.4 [3512.4, 5886.6] |
| 16 | 0 | 60/60 | 2064.2 | 2485.8 [2338.0, 2673.4] | 2719.2 [2423.6, 2794.2] | 33.84 | 50.26 | 8198.6 [5731.6, 9881.8] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.40 | 72.6 | 1370.9 | 1.40 | 100.0 | 0.0 | – | 1.2% | 79.9% | 1.04 |
| 2 | 0 | 2.25 | 88.4 | 2187.3 | 2.25 | 100.0 | 0.0 | – | 2.1% | 84.8% | 1.05 |
| 4 | 0 | 3.48 | 123.7 | 3373.4 | 3.42 | 98.3 | 0.0 | – | 4.0% | 84.8% | 1.05 |
| 8 | 0 | 3.98 | 168.7 | 3856.7 | 3.65 | 91.7 | 0.0 | – | 7.9% | 87.6% | 1.04 |
| 16 | 0 | 3.61 | 188.4 | 3512.8 | 0.18 | 5.0 | 0.0 | – | 8.1% | 87.8% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-8 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
