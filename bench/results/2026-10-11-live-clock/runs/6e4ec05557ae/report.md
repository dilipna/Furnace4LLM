# furnace-bench report `6e4ec05557ae`

- **Target:** `vllm` · model `lab` · http://localhost:8100/v1 · lab vLLM
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 20 req/level (+2 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 12214
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `4b88ff9532` · 2026-10-09T02:16:54.211076+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 20/20 | 38.4 | 53.6 [40.9, 58.3] | 57.4 [46.3, 58.3] | 10.25 | 10.61 | 1768.4 [412.3, 1853.9] |
| 2 | 0 | 20/20 | 47.4 | 66.5 [51.8, 68.3] | 67.9 [52.9, 68.3] | 14.48 | 15.64 | 1518.0 [558.8, 1759.7] |
| 4 | 0 | 20/20 | 63.9 | 106.0 [75.5, 106.9] | 106.7 [75.7, 106.9] | 15.90 | 16.80 | 2171.3 [1068.5, 4223.2] |
| 8 | 0 | 20/20 | 92.1 | 136.6 [135.6, 136.7] | 136.7 [135.9, 136.7] | 18.53 | 21.79 | 1244.3 [648.6, 2586.9] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.13 | 90.8 | 2067.5 | 2.13 | 100.0 | 0.0 | 89.1% | 0.9% | 77.7% | 1.05 |
| 2 | 0 | 3.63 | 127.0 | 3540.4 | 3.63 | 100.0 | 0.0 | 88.5% | 0.9% | 86.4% | 1.05 |
| 4 | 0 | 4.06 | 213.5 | 3991.7 | 4.06 | 100.0 | 0.0 | 87.8% | 1.2% | 88.9% | 1.04 |
| 8 | 0 | 7.73 | 247.4 | 7468.9 | 7.73 | 100.0 | 0.0 | 89.4% | 1.4% | 87.8% | 1.07 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
