# furnace-bench report `71ce793f7b00`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:19:03.220680+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 137.9 | 139.6 [139.0, 141.1] | 141.2 [139.5, 141.2] | 9.47 | 9.90 | 2148.0 [1012.1, 2373.2] |
| 2 | 0 | 60/60 | 151.6 | 256.4 [156.9, 391.3] | 317.1 [202.8, 391.3] | 16.37 | 22.47 | 2301.7 [1185.8, 3317.6] |
| 4 | 0 | 60/60 | 166.7 | 380.4 [279.4, 404.3] | 443.0 [326.1, 506.5] | 24.18 | 33.68 | 2951.7 [1631.2, 3408.2] |
| 8 | 0 | 60/60 | 175.0 | 655.6 [402.9, 888.8] | 923.0 [604.1, 979.1] | 34.51 | 52.26 | 4173.5 [3201.0, 5448.6] |
| 16 | 0 | 60/60 | 242.6 | 1546.7 [1100.5, 1751.6] | 1768.1 [1495.0, 1795.2] | 40.68 | 75.71 | 6931.1 [4739.5, 8205.3] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.61 | 83.3 | 1573.7 | 1.61 | 100.0 | 0.0 | – | 1.4% | 88.0% | 1.04 |
| 2 | 0 | 2.44 | 96.0 | 2376.1 | 2.44 | 100.0 | 0.0 | – | 2.6% | 89.5% | 1.05 |
| 4 | 0 | 3.71 | 131.9 | 3596.0 | 3.65 | 98.3 | 0.0 | – | 5.0% | 91.8% | 1.05 |
| 8 | 0 | 4.37 | 185.1 | 4231.3 | 4.00 | 91.7 | 0.0 | – | 9.7% | 92.4% | 1.04 |
| 16 | 0 | 5.52 | 287.9 | 5366.5 | 4.14 | 75.0 | 0.0 | – | 19.5% | 93.1% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-128 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
