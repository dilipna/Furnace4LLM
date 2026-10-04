# furnace-bench report `91474182777a`

- **Target:** `vllm` · model `lab` · http://localhost:8100/v1 · no shared prefix (dynamic head)
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-shape-dynamic-head` (**synthetic**)
- **Plan:** closed_loop, levels 1, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1235
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `b6dd145077` · 2026-10-04T05:43:58.558831+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 115.6 | 119.1 [116.8, 119.9] | 120.2 [118.2, 120.6] | 7.69 | 7.91 | 1122.1 [1112.4, 1134.5] |
| 4 | 0 | 60/60 | 293.1 | 408.9 [387.7, 412.8] | 423.7 [407.0, 441.5] | 10.39 | 11.64 | 1667.6 [1633.3, 1729.4] |
| 8 | 0 | 60/60 | 336.7 | 648.5 [476.0, 875.1] | 875.3 [567.6, 875.7] | 14.03 | 15.65 | 2389.7 [2208.9, 2613.8] |
| 16 | 0 | 60/60 | 367.2 | 1576.5 [1040.6, 1711.8] | 1742.8 [1438.3, 1793.6] | 21.64 | 22.95 | 4234.2 [3706.2, 4383.1] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0.91 | 117.0 | 1583.6 | 0.91 | 100.0 | 0.0 | 0.9% | 1.5% | 83.3% | 1.02 |
| 4 | 0 | 2.48 | 317.8 | 4303.6 | 2.48 | 100.0 | 0.0 | 0.9% | 6.2% | 83.4% | 1.01 |
| 8 | 0 | 3.60 | 461.2 | 6247.7 | 3.18 | 88.3 | 0.0 | 0.9% | 12.3% | 86.5% | 1.02 |
| 16 | 0 | 4.88 | 624.3 | 8457.8 | 3.01 | 61.7 | 0.0 | 0.9% | 24.4% | 89.7% | 1.02 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- Workload 'f1-shape-dynamic-head' is SYNTHETIC (source: synthetic).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
