# furnace-bench report `171f44a86240`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `979350bef2` · 2026-10-06T02:32:53.327310+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 47.3 | 58.8 [56.6, 62.0] | 64.0 [58.4, 67.3] | 11.38 | 12.02 | 2477.7 [1097.9, 2738.9] |
| 2 | 0 | 60/60 | 54.7 | 77.7 [69.2, 84.5] | 85.7 [74.3, 87.6] | 16.16 | 16.86 | 2062.4 [1023.5, 3035.6] |
| 4 | 0 | 60/60 | 77.0 | 100.7 [92.7, 112.3] | 111.9 [99.9, 112.3] | 17.98 | 19.29 | 2071.8 [1087.6, 2540.5] |
| 8 | 0 | 60/60 | 87.0 | 176.5 [122.8, 177.7] | 177.7 [176.3, 177.8] | 20.67 | 23.69 | 2659.6 [2040.1, 2963.9] |
| 16 | 0 | 60/60 | 1039.3 | 1491.3 [1344.0, 1519.1] | 1578.5 [1480.7, 1675.9] | 19.98 | 22.35 | 5327.8 [3371.5, 5417.7] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.59 | 81.9 | 1547.9 | 1.59 | 100.0 | 0.0 | 88.5% | 1.2% | 72.9% | 1.04 |
| 2 | 0 | 2.92 | 115.0 | 2847.0 | 2.92 | 100.0 | 0.0 | 88.7% | 1.3% | 80.0% | 1.05 |
| 4 | 0 | 5.48 | 194.9 | 5314.2 | 5.48 | 100.0 | 0.0 | 89.1% | 1.5% | 80.7% | 1.05 |
| 8 | 0 | 6.84 | 289.9 | 6627.2 | 6.84 | 100.0 | 0.0 | 89.2% | 2.1% | 79.5% | 1.04 |
| 16 | 0 | 5.79 | 302.0 | 5629.2 | 0.77 | 13.3 | 0.0 | 88.8% | 2.3% | 80.3% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-8 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
