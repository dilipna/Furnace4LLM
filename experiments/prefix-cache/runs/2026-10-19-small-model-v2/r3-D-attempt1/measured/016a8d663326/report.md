# furnace-bench report `016a8d663326`

- **Target:** `vllm` · model `lab` · http://127.0.0.1:8115/v1 · D
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `synthetic-ops-runbook` (**synthetic**)
- **Plan:** closed_loop, levels 1, 60 req/level (+0 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 7
- **SLO:** TTFT ≤ – ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `157736bb81` · 2026-10-19T05:41:14.710219+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 43.3 | 52.9 [46.7, 210.3] | 756.2 [52.1, 1650.9] | 10.19 | 10.73 | 387.8 [368.4, 502.6] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.57 | 82.2 | 4109.2 | – | – | 0.0 | 94.0% | 1.2% | 76.8% | 1.00 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- Workload 'synthetic-ops-runbook' is SYNTHETIC (source: synthetic).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
