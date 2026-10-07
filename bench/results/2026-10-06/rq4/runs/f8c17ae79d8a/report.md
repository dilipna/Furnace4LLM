# furnace-bench report `f8c17ae79d8a`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1236
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `cd47fbfda0` · 2026-10-07T01:00:53.791400+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 34.7 | 48.9 [47.0, 49.2] | 49.8 [48.4, 50.6] | 9.65 | 9.99 | 1229.3 [464.2, 1765.0] |
| 2 | 0 | 60/60 | 48.9 | 65.7 [60.7, 68.4] | 69.2 [63.7, 70.5] | 14.63 | 15.34 | 1611.8 [1337.2, 1926.8] |
| 4 | 0 | 60/60 | 59.8 | 86.7 [73.1, 98.5] | 98.5 [85.2, 98.5] | 15.67 | 17.51 | 2344.3 [1112.6, 3382.7] |
| 8 | 0 | 60/60 | 74.9 | 169.2 [97.0, 170.1] | 170.5 [168.9, 171.3] | 17.98 | 20.34 | 3878.1 [2521.1, 4116.0] |
| 16 | 0 | 60/60 | 105.0 | 294.3 [290.5, 294.5] | 294.5 [293.9, 294.5] | 26.06 | 28.81 | 3623.4 [2287.5, 4422.3] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.70 | 96.0 | 2632.1 | 2.70 | 100.0 | 0.0 | 88.7% | 1.0% | 83.7% | 1.05 |
| 2 | 0 | 3.13 | 127.2 | 3032.9 | 3.13 | 100.0 | 0.0 | 89.1% | 1.1% | 86.5% | 1.05 |
| 4 | 0 | 5.56 | 235.3 | 5416.4 | 5.56 | 100.0 | 0.0 | 88.7% | 1.5% | 90.0% | 1.04 |
| 8 | 0 | 6.38 | 378.4 | 6178.7 | 6.38 | 100.0 | 0.0 | 89.3% | 2.0% | 90.4% | 1.04 |
| 16 | 0 | 9.50 | 426.6 | 9229.2 | 9.50 | 100.0 | 0.0 | 88.9% | 2.8% | 91.6% | 1.05 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-32 repeat=2

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
