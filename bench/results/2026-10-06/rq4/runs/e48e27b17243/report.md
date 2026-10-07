# furnace-bench report `e48e27b17243`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1236
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `f2ab5fd7eb` · 2026-10-07T00:46:47.595966+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 137.8 | 139.1 [138.7, 139.8] | 140.6 [139.1, 141.8] | 9.41 | 9.83 | 1275.4 [533.9, 1845.9] |
| 2 | 0 | 60/60 | 151.7 | 265.6 [157.5, 266.8] | 268.5 [257.2, 271.3] | 14.76 | 21.34 | 1891.6 [1626.4, 2394.3] |
| 4 | 0 | 60/60 | 164.1 | 289.2 [269.9, 416.5] | 452.6 [282.4, 511.6] | 22.55 | 33.02 | 3210.4 [2070.4, 5292.7] |
| 8 | 0 | 60/60 | 176.0 | 655.4 [311.4, 880.2] | 910.9 [630.6, 961.2] | 30.07 | 51.07 | 6589.3 [3741.7, 7445.0] |
| 16 | 0 | 60/60 | 1824.4 | 2244.4 [2077.9, 2539.0] | 2647.3 [2205.8, 2824.8] | 33.06 | 47.64 | 6812.6 [5537.2, 8987.0] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.15 | 76.5 | 2098.7 | 2.15 | 100.0 | 0.0 | – | 1.1% | 89.4% | 1.05 |
| 2 | 0 | 2.39 | 97.3 | 2321.0 | 2.39 | 100.0 | 0.0 | – | 2.1% | 91.4% | 1.05 |
| 4 | 0 | 3.53 | 149.3 | 3438.2 | 3.47 | 98.3 | 0.0 | – | 4.1% | 91.4% | 1.05 |
| 8 | 0 | 3.84 | 227.8 | 3719.1 | 3.52 | 91.7 | 0.0 | – | 8.0% | 90.3% | 1.04 |
| 16 | 0 | 4.31 | 193.7 | 4189.9 | 0.22 | 5.0 | 0.0 | – | 8.0% | 93.8% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-8 repeat=2

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
