# furnace-bench report `c96109bad788`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1235
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `af8e9f49e7` · 2026-10-07T00:29:11.811446+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 138.0 | 139.9 [139.6, 144.5] | 142.1 [139.8, 144.5] | 9.64 | 10.22 | 1127.7 [712.2, 1698.1] |
| 2 | 0 | 60/60 | 150.6 | 258.7 [154.8, 269.4] | 270.8 [203.2, 273.2] | 15.79 | 21.88 | 3176.3 [1836.4, 3721.6] |
| 4 | 0 | 60/60 | 163.4 | 383.8 [279.1, 505.2] | 444.8 [329.9, 505.2] | 21.45 | 32.00 | 3990.1 [2207.8, 4957.8] |
| 8 | 0 | 60/60 | 198.2 | 647.9 [391.4, 871.7] | 895.5 [617.7, 934.4] | 34.06 | 48.12 | 4704.2 [1995.0, 5424.4] |
| 16 | 0 | 60/60 | 1424.5 | 1987.5 [1741.0, 2279.3] | 2317.8 [1911.1, 2385.3] | 31.66 | 45.56 | 4240.4 [3174.1, 5129.3] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.13 | 75.1 | 2062.1 | 2.13 | 100.0 | 0.0 | – | 1.2% | 87.1% | 1.04 |
| 2 | 0 | 2.10 | 102.4 | 2064.1 | 2.10 | 100.0 | 0.0 | – | 2.3% | 91.1% | 1.03 |
| 4 | 0 | 3.04 | 149.8 | 2969.6 | 2.99 | 98.3 | 0.0 | – | 4.2% | 92.1% | 1.03 |
| 8 | 0 | 5.18 | 189.6 | 5040.4 | 4.75 | 91.7 | 0.0 | – | 7.9% | 93.1% | 1.04 |
| 16 | 0 | 4.89 | 187.6 | 4759.7 | 0.24 | 5.0 | 0.0 | – | 7.9% | 93.2% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-8 repeat=1

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
