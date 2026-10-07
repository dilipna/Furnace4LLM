# furnace-bench report `4dfbc2f07447`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1236
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `cd47fbfda0` · 2026-10-07T00:57:40.194883+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 33.9 | 48.4 [45.7, 48.8] | 49.3 [47.8, 50.0] | 9.37 | 10.21 | 1183.3 [454.8, 1748.4] |
| 2 | 0 | 60/60 | 48.2 | 62.8 [59.9, 68.6] | 69.8 [62.6, 71.9] | 14.47 | 15.41 | 1595.6 [1210.5, 1898.0] |
| 4 | 0 | 60/60 | 61.3 | 85.7 [75.3, 103.2] | 103.3 [83.9, 103.4] | 15.94 | 17.43 | 2379.0 [1149.0, 3413.1] |
| 8 | 0 | 60/60 | 74.5 | 167.4 [98.7, 169.9] | 170.1 [167.1, 170.4] | 17.90 | 20.24 | 3908.7 [2552.3, 4087.5] |
| 16 | 0 | 60/60 | 891.6 | 1136.9 [1087.6, 1149.6] | 1156.6 [1126.2, 1168.1] | 19.04 | 21.61 | 3621.9 [2688.6, 4766.8] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.75 | 97.6 | 2677.6 | 2.75 | 100.0 | 0.0 | 88.7% | 1.1% | 86.5% | 1.05 |
| 2 | 0 | 3.32 | 134.7 | 3213.1 | 3.32 | 100.0 | 0.0 | 89.1% | 1.2% | 86.8% | 1.05 |
| 4 | 0 | 5.48 | 231.9 | 5337.9 | 5.48 | 100.0 | 0.0 | 88.7% | 1.7% | 88.5% | 1.04 |
| 8 | 0 | 6.37 | 377.3 | 6161.2 | 6.37 | 100.0 | 0.0 | 89.3% | 2.3% | 90.1% | 1.04 |
| 16 | 0 | 7.64 | 343.0 | 7420.8 | 1.02 | 13.3 | 0.0 | 88.9% | 2.1% | 88.6% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-8 repeat=2

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
