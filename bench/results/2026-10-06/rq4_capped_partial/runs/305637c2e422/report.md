# furnace-bench report `305637c2e422`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-128
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `03c6b6279b` · 2026-10-06T03:36:35.609111+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 35.2 | 50.0 [48.1, 50.3] | 50.8 [49.7, 51.7] | 9.81 | 10.16 | 2117.4 [961.0, 2258.9] |
| 2 | 0 | 60/60 | 48.7 | 60.9 [59.3, 71.6] | 72.0 [60.0, 72.6] | 14.58 | 15.07 | 1814.8 [898.7, 2681.1] |
| 4 | 0 | 60/60 | 61.6 | 92.2 [77.3, 96.4] | 96.2 [91.2, 96.4] | 16.21 | 17.92 | 1877.9 [976.1, 2283.0] |
| 8 | 0 | 60/60 | 76.3 | 161.6 [110.5, 162.5] | 162.1 [161.0, 162.5] | 18.44 | 21.06 | 2340.2 [1822.0, 2630.9] |
| 16 | 0 | 60/60 | 115.9 | 308.9 [182.4, 309.2] | 309.2 [308.7, 309.3] | 24.84 | 29.93 | 4304.9 [2906.2, 4561.2] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.87 | 96.4 | 1821.1 | 1.87 | 100.0 | 0.0 | 88.5% | 1.4% | 83.9% | 1.04 |
| 2 | 0 | 3.27 | 128.7 | 3185.3 | 3.27 | 100.0 | 0.0 | 88.7% | 1.6% | 88.2% | 1.05 |
| 4 | 0 | 6.12 | 217.8 | 5939.8 | 6.12 | 100.0 | 0.0 | 89.1% | 1.9% | 88.8% | 1.05 |
| 8 | 0 | 7.73 | 327.5 | 7487.8 | 7.73 | 100.0 | 0.0 | 89.2% | 2.5% | 90.6% | 1.04 |
| 16 | 0 | 8.54 | 445.7 | 8308.1 | 8.54 | 100.0 | 0.0 | 88.8% | 4.2% | 91.2% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-128 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
