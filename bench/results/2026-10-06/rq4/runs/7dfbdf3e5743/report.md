# furnace-bench report `7dfbdf3e5743`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:11:27.726677+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 138.0 | 141.9 [139.8, 145.2] | 159.6 [141.3, 183.3] | 9.49 | 10.07 | 2147.6 [1027.7, 2354.2] |
| 2 | 0 | 60/60 | 152.6 | 263.3 [158.5, 270.6] | 271.6 [162.0, 273.2] | 15.62 | 21.46 | 2469.9 [1249.6, 3286.5] |
| 4 | 0 | 60/60 | 165.1 | 388.1 [281.8, 407.0] | 445.8 [330.5, 509.4] | 23.53 | 32.75 | 2890.1 [1651.9, 3317.3] |
| 8 | 0 | 60/60 | 175.3 | 656.1 [403.1, 882.8] | 916.3 [598.3, 971.2] | 34.92 | 52.99 | 4265.8 [3229.0, 5346.9] |
| 16 | 0 | 60/60 | 1882.0 | 2434.6 [2342.7, 2472.8] | 2563.9 [2418.1, 2713.3] | 32.06 | 49.79 | 7690.0 [5626.9, 8904.1] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.61 | 83.1 | 1569.9 | 1.61 | 100.0 | 0.0 | – | 1.2% | 87.0% | 1.04 |
| 2 | 0 | 2.42 | 95.4 | 2361.0 | 2.42 | 100.0 | 0.0 | – | 2.1% | 90.1% | 1.05 |
| 4 | 0 | 3.78 | 134.4 | 3664.0 | 3.71 | 98.3 | 0.0 | – | 4.0% | 91.6% | 1.05 |
| 8 | 0 | 4.34 | 183.7 | 4201.2 | 3.98 | 91.7 | 0.0 | – | 7.9% | 93.5% | 1.04 |
| 16 | 0 | 3.88 | 202.7 | 3778.9 | 0.19 | 5.0 | 0.0 | – | 8.1% | 93.3% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-8 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
