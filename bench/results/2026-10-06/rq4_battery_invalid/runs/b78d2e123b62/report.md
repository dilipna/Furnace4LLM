# furnace-bench report `b78d2e123b62`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `979350bef2` · 2026-10-06T02:37:11.783609+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 45.7 | 58.3 [56.8, 63.8] | 63.8 [57.6, 63.9] | 11.29 | 12.04 | 2491.2 [1080.4, 2551.1] |
| 2 | 0 | 60/60 | 56.8 | 72.6 [66.9, 80.0] | 81.5 [71.6, 84.0] | 15.99 | 16.87 | 2035.2 [985.7, 2921.1] |
| 4 | 0 | 60/60 | 68.9 | 99.2 [87.0, 99.9] | 102.6 [99.0, 107.1] | 17.92 | 20.24 | 2129.3 [1101.9, 2529.7] |
| 8 | 0 | 60/60 | 84.8 | 181.2 [124.1, 183.1] | 182.7 [179.2, 183.1] | 20.34 | 23.77 | 2623.6 [2013.5, 2922.2] |
| 16 | 0 | 60/60 | 122.6 | 322.2 [320.0, 323.1] | 323.2 [321.5, 323.3] | 26.45 | 33.37 | 4728.1 [3189.1, 5013.1] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.61 | 83.1 | 1570.4 | 1.61 | 100.0 | 0.0 | 88.5% | 1.0% | 73.8% | 1.04 |
| 2 | 0 | 2.95 | 116.2 | 2874.4 | 2.95 | 100.0 | 0.0 | 88.7% | 1.1% | 80.9% | 1.05 |
| 4 | 0 | 5.48 | 195.0 | 5316.3 | 5.48 | 100.0 | 0.0 | 89.1% | 1.3% | 80.6% | 1.05 |
| 8 | 0 | 6.97 | 295.2 | 6748.8 | 6.97 | 100.0 | 0.0 | 89.2% | 1.8% | 83.7% | 1.04 |
| 16 | 0 | 7.72 | 402.8 | 7508.8 | 7.72 | 100.0 | 0.0 | 88.8% | 2.9% | 82.2% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-32 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
