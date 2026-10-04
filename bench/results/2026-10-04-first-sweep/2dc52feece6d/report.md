# furnace-bench report `2dc52feece6d`

- **Target:** `vllm` · model `lab` · http://localhost:8100/v1 · vllm 0.30 qwen2.5-0.5b prefix-cache=on (default)
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `shared-prefix-512` (**synthetic**)
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 300 ms · TPOT ≤ 50 ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `b7925209cb` · 2026-10-04T04:54:13.897086+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 45.6 | 77.0 [60.8, 103.1] | 152.8 [71.8, 234.2] | 10.91 | 12.18 | 1602.4 [1504.0, 2873.0] |
| 2 | 0 | 60/60 | 66.6 | 93.3 [84.3, 97.6] | 101.8 [91.8, 108.5] | 12.48 | 12.83 | 1724.9 [1705.2, 1728.7] |
| 4 | 0 | 60/60 | 86.6 | 120.4 [105.3, 136.1] | 136.3 [119.6, 136.5] | 13.00 | 13.34 | 1789.7 [1774.7, 1792.4] |
| 8 | 0 | 60/60 | 156.4 | 260.6 [181.8, 261.3] | 261.4 [260.6, 261.6] | 13.76 | 17.82 | 2522.1 [2048.5, 2524.9] |
| 16 | 0 | 60/60 | 205.0 | 389.3 [387.8, 390.2] | 390.4 [388.9, 390.7] | 15.00 | 15.83 | 2256.7 [2254.3, 2258.3] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0.67 | 85.5 | 353.4 | 0.67 | 100.0 | 0.0 | 72.6% | 0.5% | 68.2% | 1.02 |
| 2 | 0 | 1.21 | 154.3 | 638.3 | 1.21 | 100.0 | 0.0 | 72.5% | 0.8% | 75.7% | 1.03 |
| 4 | 0 | 2.29 | 293.6 | 1215.5 | 2.29 | 100.0 | 0.0 | 72.5% | 1.2% | 76.0% | 1.02 |
| 8 | 0 | 3.79 | 485.5 | 2010.1 | 3.79 | 100.0 | 0.0 | 72.5% | 2.1% | 68.4% | 1.02 |
| 16 | 0 | 6.98 | 894.0 | 3701.7 | 5.94 | 85.0 | 0.0 | 72.5% | 3.9% | 77.8% | 1.02 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- Workload 'shared-prefix-512' is SYNTHETIC (source: synthetic).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
