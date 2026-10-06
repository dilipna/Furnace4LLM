# furnace-bench report `9be39d998060`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `03c6b6279b` · 2026-10-06T03:30:02.851822+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 34.3 | 48.4 [47.3, 49.4] | 49.5 [48.3, 49.7] | 9.65 | 10.04 | 2073.5 [939.9, 2305.9] |
| 2 | 0 | 60/60 | 47.3 | 61.4 [59.0, 69.1] | 70.7 [60.4, 73.2] | 14.23 | 14.95 | 1797.0 [881.5, 2655.7] |
| 4 | 0 | 60/60 | 60.5 | 85.4 [73.4, 94.8] | 95.0 [83.1, 95.3] | 16.07 | 17.18 | 1862.4 [974.3, 2217.6] |
| 8 | 0 | 60/60 | 76.2 | 160.6 [111.7, 161.5] | 161.3 [158.8, 161.5] | 18.71 | 21.75 | 2406.6 [1853.3, 2678.7] |
| 16 | 0 | 60/60 | 994.7 | 1342.7 [1260.6, 1373.9] | 1396.1 [1315.4, 1432.5] | 18.18 | 20.46 | 4840.9 [3068.1, 4931.1] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.89 | 97.9 | 1850.0 | 1.89 | 100.0 | 0.0 | 88.5% | 1.2% | 84.6% | 1.04 |
| 2 | 0 | 3.33 | 131.0 | 3242.4 | 3.33 | 100.0 | 0.0 | 88.7% | 1.3% | 89.8% | 1.05 |
| 4 | 0 | 6.19 | 220.1 | 6001.0 | 6.19 | 100.0 | 0.0 | 89.1% | 1.6% | 90.4% | 1.05 |
| 8 | 0 | 7.56 | 320.2 | 7320.9 | 7.56 | 100.0 | 0.0 | 89.2% | 2.1% | 89.0% | 1.04 |
| 16 | 0 | 6.38 | 333.2 | 6210.4 | 0.96 | 15.0 | 0.0 | 88.8% | 2.4% | 88.2% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-8 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
