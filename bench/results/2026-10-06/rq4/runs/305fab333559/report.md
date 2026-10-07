# furnace-bench report `305fab333559`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1235
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:22:43.125308+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 34.7 | 47.2 [46.4, 48.2] | 49.4 [47.0, 51.6] | 9.49 | 9.95 | 1027.7 [565.1, 1618.0] |
| 2 | 0 | 60/60 | 47.9 | 63.8 [60.2, 69.9] | 71.6 [62.2, 74.5] | 14.70 | 15.40 | 3067.3 [1494.2, 3352.7] |
| 4 | 0 | 60/60 | 63.3 | 81.1 [75.4, 97.9] | 98.2 [79.5, 98.8] | 16.14 | 18.17 | 3225.5 [1581.7, 3742.4] |
| 8 | 0 | 60/60 | 85.3 | 155.5 [115.6, 155.8] | 155.7 [155.3, 155.8] | 19.76 | 21.85 | 2431.1 [1289.2, 2826.7] |
| 16 | 0 | 60/60 | 129.9 | 252.6 [247.8, 304.0] | 304.3 [249.5, 304.7] | 27.87 | 31.21 | 2496.5 [1712.5, 3159.2] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.75 | 96.8 | 2656.9 | 2.75 | 100.0 | 0.0 | 89.3% | 1.0% | 85.8% | 1.04 |
| 2 | 0 | 2.61 | 127.1 | 2563.1 | 2.61 | 100.0 | 0.0 | 88.1% | 1.3% | 87.7% | 1.03 |
| 4 | 0 | 4.29 | 211.1 | 4184.9 | 4.29 | 100.0 | 0.0 | 88.5% | 1.5% | 87.0% | 1.03 |
| 8 | 0 | 8.76 | 320.9 | 8533.4 | 8.76 | 100.0 | 0.0 | 88.7% | 1.8% | 86.0% | 1.03 |
| 16 | 0 | 9.41 | 361.0 | 9157.3 | 9.41 | 100.0 | 0.0 | 88.7% | 2.7% | 89.5% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-32 repeat=1

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
