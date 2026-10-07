# furnace-bench report `4ae2a9cd3cc0`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1236
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `83c66c2025` · 2026-10-07T00:54:08.700674+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 137.6 | 139.9 [139.5, 142.8] | 142.8 [139.9, 142.8] | 9.55 | 9.84 | 1307.1 [546.6, 1855.7] |
| 2 | 0 | 60/60 | 150.7 | 264.6 [157.8, 272.5] | 272.9 [255.1, 273.5] | 14.51 | 20.96 | 1843.5 [1579.6, 2339.8] |
| 4 | 0 | 60/60 | 164.6 | 282.5 [268.9, 396.8] | 435.3 [276.3, 498.4] | 22.59 | 31.66 | 3295.4 [1987.1, 5374.1] |
| 8 | 0 | 60/60 | 172.6 | 661.8 [300.4, 887.1] | 922.5 [600.7, 980.6] | 30.37 | 52.57 | 6502.5 [3789.4, 7541.1] |
| 16 | 0 | 60/60 | 247.9 | 1541.0 [1105.5, 1738.9] | 1751.9 [1489.3, 1773.4] | 45.07 | 74.62 | 6681.6 [3533.0, 7198.8] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.13 | 75.8 | 2078.8 | 2.13 | 100.0 | 0.0 | – | 1.4% | 88.8% | 1.05 |
| 2 | 0 | 2.45 | 99.5 | 2372.1 | 2.45 | 100.0 | 0.0 | – | 2.5% | 91.9% | 1.05 |
| 4 | 0 | 3.50 | 148.2 | 3411.6 | 3.50 | 100.0 | 0.0 | – | 5.1% | 91.1% | 1.05 |
| 8 | 0 | 3.87 | 229.5 | 3747.2 | 3.55 | 91.7 | 0.0 | – | 9.9% | 93.8% | 1.04 |
| 16 | 0 | 5.90 | 264.8 | 5729.7 | 4.62 | 78.3 | 0.0 | – | 19.4% | 92.9% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-128 repeat=2

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
