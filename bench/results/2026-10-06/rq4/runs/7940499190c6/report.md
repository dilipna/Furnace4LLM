# furnace-bench report `7940499190c6`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1235
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:25:55.671576+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 34.3 | 48.3 [46.5, 48.9] | 49.7 [48.1, 50.9] | 9.57 | 10.04 | 1021.1 [573.1, 1593.7] |
| 2 | 0 | 60/60 | 47.7 | 64.7 [59.2, 70.2] | 71.8 [64.0, 74.4] | 14.47 | 15.04 | 3019.4 [1449.2, 3312.0] |
| 4 | 0 | 60/60 | 61.9 | 83.5 [75.5, 108.5] | 108.7 [80.8, 108.9] | 16.19 | 18.09 | 3281.6 [1568.6, 3759.2] |
| 8 | 0 | 60/60 | 85.0 | 157.8 [115.8, 158.1] | 158.3 [157.5, 158.5] | 19.65 | 21.88 | 2478.9 [1287.1, 2851.0] |
| 16 | 0 | 60/60 | 130.0 | 302.7 [301.8, 303.1] | 303.4 [302.6, 303.9] | 27.65 | 31.99 | 2524.5 [1669.7, 3258.5] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.73 | 96.3 | 2644.3 | 2.73 | 100.0 | 0.0 | 89.3% | 1.5% | 83.1% | 1.04 |
| 2 | 0 | 2.65 | 129.0 | 2600.6 | 2.65 | 100.0 | 0.0 | 88.1% | 1.8% | 87.8% | 1.03 |
| 4 | 0 | 4.27 | 210.2 | 4165.4 | 4.27 | 100.0 | 0.0 | 88.5% | 2.1% | 86.1% | 1.03 |
| 8 | 0 | 8.72 | 319.2 | 8486.2 | 8.72 | 100.0 | 0.0 | 88.7% | 2.5% | 86.1% | 1.03 |
| 16 | 0 | 9.27 | 355.7 | 9023.2 | 9.27 | 100.0 | 0.0 | 88.7% | 3.9% | 88.7% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-128 repeat=1

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
