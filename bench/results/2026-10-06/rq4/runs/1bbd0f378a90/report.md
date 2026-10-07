# furnace-bench report `1bbd0f378a90`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:15:15.481876+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 139.9 | 145.5 [142.1, 146.4] | 146.6 [143.7, 147.1] | 9.79 | 10.35 | 2209.5 [1054.8, 2409.5] |
| 2 | 0 | 60/60 | 152.3 | 262.2 [160.6, 266.1] | 267.7 [261.7, 270.4] | 15.24 | 21.83 | 2387.0 [1200.7, 3284.1] |
| 4 | 0 | 60/60 | 168.1 | 387.5 [285.7, 407.7] | 447.8 [333.3, 513.5] | 24.12 | 33.47 | 2942.9 [1670.5, 3385.4] |
| 8 | 0 | 60/60 | 180.5 | 640.9 [389.1, 867.4] | 900.5 [628.2, 954.7] | 34.79 | 53.71 | 4259.4 [3232.8, 5381.4] |
| 16 | 0 | 60/60 | 252.2 | 1539.3 [1107.1, 1743.3] | 1760.5 [1402.6, 1788.8] | 43.95 | 77.38 | 6995.1 [4717.8, 8421.0] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.56 | 80.9 | 1527.4 | 1.56 | 100.0 | 0.0 | – | 1.0% | 85.4% | 1.04 |
| 2 | 0 | 2.43 | 95.5 | 2362.4 | 2.43 | 100.0 | 0.0 | – | 1.8% | 89.6% | 1.05 |
| 4 | 0 | 3.72 | 132.3 | 3607.4 | 3.66 | 98.3 | 0.0 | – | 3.5% | 92.2% | 1.05 |
| 8 | 0 | 4.33 | 183.5 | 4195.5 | 3.90 | 90.0 | 0.0 | – | 6.8% | 92.8% | 1.04 |
| 16 | 0 | 5.38 | 280.8 | 5234.2 | 4.21 | 78.3 | 0.0 | – | 13.7% | 92.4% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-32 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
