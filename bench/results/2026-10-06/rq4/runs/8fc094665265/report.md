# furnace-bench report `8fc094665265`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:08:06.255013+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 34.6 | 49.7 [47.8, 50.2] | 50.5 [49.2, 50.9] | 9.75 | 10.15 | 2131.9 [976.5, 2342.1] |
| 2 | 0 | 60/60 | 48.1 | 62.6 [60.0, 68.4] | 70.1 [61.9, 73.0] | 14.46 | 15.12 | 1798.2 [885.6, 2689.0] |
| 4 | 0 | 60/60 | 60.1 | 88.5 [73.6, 92.7] | 92.9 [83.9, 93.1] | 16.23 | 17.29 | 1891.9 [995.2, 2262.1] |
| 8 | 0 | 60/60 | 75.9 | 163.5 [112.3, 165.0] | 164.6 [160.7, 165.0] | 18.55 | 21.22 | 2385.7 [1832.4, 2669.7] |
| 16 | 0 | 60/60 | 114.5 | 312.7 [311.6, 313.2] | 313.4 [312.5, 313.7] | 24.94 | 31.54 | 4348.2 [2945.8, 4629.1] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.86 | 96.1 | 1815.2 | 1.86 | 100.0 | 0.0 | 88.5% | 1.4% | 84.2% | 1.04 |
| 2 | 0 | 3.29 | 129.4 | 3201.2 | 3.29 | 100.0 | 0.0 | 88.7% | 1.6% | 88.5% | 1.05 |
| 4 | 0 | 6.12 | 217.7 | 5937.4 | 6.12 | 100.0 | 0.0 | 89.1% | 2.0% | 88.9% | 1.05 |
| 8 | 0 | 7.63 | 323.4 | 7393.6 | 7.63 | 100.0 | 0.0 | 89.2% | 2.6% | 88.6% | 1.04 |
| 16 | 0 | 8.42 | 439.3 | 8189.5 | 8.42 | 100.0 | 0.0 | 88.8% | 4.3% | 89.7% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-128 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
