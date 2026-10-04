# furnace-bench report `21111ede417c`

- **Target:** `vllm` · model `lab` · http://localhost:8100/v1 · shared 1000-token prefix (prefix-stable prompt)
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-shape-prefix-stable` (**synthetic**)
- **Plan:** closed_loop, levels 1, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `b6dd145077` · 2026-10-04T05:41:50.388129+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 65.2 | 70.1 [67.0, 71.5] | 71.7 [69.8, 71.9] | 7.70 | 7.97 | 1078.3 [1068.6, 1085.5] |
| 4 | 0 | 60/60 | 174.2 | 212.9 [206.5, 213.7] | 213.7 [209.5, 213.7] | 9.07 | 9.86 | 1340.4 [1338.5, 1344.1] |
| 8 | 0 | 60/60 | 254.9 | 374.3 [340.9, 396.7] | 397.0 [355.9, 397.5] | 10.45 | 11.85 | 1645.0 [1620.9, 1662.3] |
| 16 | 0 | 60/60 | 369.5 | 752.1 [520.9, 754.9] | 767.8 [669.9, 788.8] | 13.46 | 15.12 | 2395.7 [2217.4, 2404.1] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0.95 | 122.1 | 1637.6 | 0.95 | 100.0 | 0.0 | 58.7% | 1.5% | 82.1% | 1.02 |
| 4 | 0 | 3.01 | 384.9 | 5164.9 | 3.01 | 100.0 | 0.0 | 58.7% | 3.6% | 84.3% | 1.02 |
| 8 | 0 | 4.78 | 611.9 | 8212.2 | 4.78 | 100.0 | 0.0 | 58.7% | 6.4% | 87.2% | 1.02 |
| 16 | 0 | 7.29 | 933.6 | 12530.3 | 5.83 | 80.0 | 0.0 | 58.7% | 12.0% | 89.6% | 1.02 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- Workload 'f1-shape-prefix-stable' is SYNTHETIC (source: synthetic).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
