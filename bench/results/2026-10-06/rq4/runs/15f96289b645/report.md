# furnace-bench report `15f96289b645`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1236
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `f2ab5fd7eb` · 2026-10-07T00:43:45.323400+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 34.9 | 50.5 [48.4, 51.1] | 51.7 [49.8, 52.8] | 9.65 | 10.36 | 1270.3 [477.8, 1823.3] |
| 2 | 0 | 60/60 | 48.7 | 64.1 [59.7, 77.1] | 73.8 [62.7, 77.1] | 14.88 | 15.46 | 1631.5 [1370.1, 1953.7] |
| 4 | 0 | 60/60 | 62.0 | 89.3 [75.1, 104.5] | 104.5 [88.2, 104.5] | 16.25 | 17.71 | 2461.0 [1175.0, 3540.4] |
| 8 | 0 | 60/60 | 76.8 | 140.3 [105.8, 188.7] | 189.1 [140.0, 189.7] | 18.49 | 21.30 | 4013.8 [2647.0, 4202.4] |
| 16 | 0 | 60/60 | 105.5 | 298.5 [293.7, 300.1] | 299.4 [297.1, 300.1] | 26.15 | 28.91 | 3714.2 [2326.2, 4486.4] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.67 | 94.7 | 2597.5 | 2.67 | 100.0 | 0.0 | 88.7% | 1.4% | 83.0% | 1.05 |
| 2 | 0 | 3.10 | 126.1 | 3007.5 | 3.10 | 100.0 | 0.0 | 89.1% | 1.6% | 86.6% | 1.05 |
| 4 | 0 | 5.33 | 225.8 | 5197.8 | 5.33 | 100.0 | 0.0 | 88.7% | 2.1% | 85.8% | 1.04 |
| 8 | 0 | 6.18 | 366.1 | 5977.6 | 6.18 | 100.0 | 0.0 | 89.3% | 2.8% | 88.5% | 1.03 |
| 16 | 0 | 9.33 | 419.2 | 9070.0 | 9.33 | 100.0 | 0.0 | 88.9% | 4.0% | 89.3% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-128 repeat=2

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
