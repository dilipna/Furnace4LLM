# furnace-bench report `b96e026fa342`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1235
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `9cae609e87` · 2026-10-07T00:36:42.636520+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 138.9 | 143.1 [140.9, 147.2] | 146.2 [142.8, 147.2] | 9.87 | 10.30 | 1149.1 [701.9, 1745.3] |
| 2 | 0 | 60/60 | 152.0 | 261.1 [156.9, 267.5] | 268.4 [204.7, 270.1] | 15.96 | 21.81 | 3242.4 [1868.5, 3763.5] |
| 4 | 0 | 60/60 | 163.3 | 284.7 [270.4, 396.9] | 435.3 [276.6, 498.3] | 21.28 | 32.96 | 3972.4 [2208.4, 4850.4] |
| 8 | 0 | 60/60 | 259.9 | 649.9 [398.5, 879.3] | 903.6 [621.9, 943.5] | 35.17 | 54.95 | 4989.6 [2184.6, 5794.5] |
| 16 | 0 | 60/60 | 312.5 | 1549.5 [1113.8, 1750.3] | 1766.3 [1498.2, 1792.6] | 49.05 | 77.33 | 4074.3 [3028.4, 5403.0] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.10 | 73.9 | 2028.7 | 2.10 | 100.0 | 0.0 | – | 1.4% | 85.7% | 1.04 |
| 2 | 0 | 2.08 | 101.0 | 2036.9 | 2.08 | 100.0 | 0.0 | – | 2.8% | 89.4% | 1.03 |
| 4 | 0 | 3.07 | 151.3 | 2998.1 | 3.07 | 100.0 | 0.0 | – | 5.2% | 92.8% | 1.03 |
| 8 | 0 | 4.86 | 178.1 | 4736.5 | 4.46 | 91.7 | 0.0 | – | 9.7% | 93.1% | 1.04 |
| 16 | 0 | 5.99 | 229.9 | 5831.5 | 4.69 | 78.3 | 0.0 | – | 19.2% | 91.9% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-128 repeat=1

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
