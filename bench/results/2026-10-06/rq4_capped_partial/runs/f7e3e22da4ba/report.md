# furnace-bench report `f7e3e22da4ba`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `03c6b6279b` · 2026-10-06T03:43:24.222682+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 138.8 | 142.2 [140.5, 143.4] | 143.8 [142.1, 144.4] | 9.64 | 10.13 | 2158.9 [1041.8, 2386.2] |
| 2 | 0 | 60/60 | 153.5 | 257.5 [156.7, 276.6] | 271.3 [162.2, 276.6] | 15.36 | 22.06 | 2484.6 [1250.5, 3299.1] |
| 4 | 0 | 60/60 | 166.1 | 399.0 [273.1, 407.2] | 446.1 [329.3, 510.0] | 23.52 | 33.26 | 2939.5 [1639.7, 3354.9] |
| 8 | 0 | 60/60 | 179.9 | 659.5 [412.4, 883.5] | 915.0 [594.1, 966.6] | 33.89 | 52.52 | 4200.1 [3249.3, 5354.4] |
| 16 | 0 | 60/60 | 266.8 | 1560.6 [1106.6, 1763.3] | 1780.0 [1506.7, 1807.4] | 41.79 | 79.22 | 7233.8 [5003.0, 8694.9] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.59 | 82.1 | 1551.1 | 1.59 | 100.0 | 0.0 | – | 1.0% | 88.0% | 1.04 |
| 2 | 0 | 2.41 | 94.9 | 2349.7 | 2.41 | 100.0 | 0.0 | – | 1.8% | 90.1% | 1.05 |
| 4 | 0 | 3.75 | 133.4 | 3638.1 | 3.69 | 98.3 | 0.0 | – | 3.5% | 93.1% | 1.05 |
| 8 | 0 | 4.38 | 185.4 | 4238.1 | 4.01 | 91.7 | 0.0 | – | 6.8% | 92.8% | 1.04 |
| 16 | 0 | 5.25 | 274.1 | 5109.3 | 4.11 | 78.3 | 0.0 | – | 13.7% | 93.8% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-32 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
