# furnace-bench report `48da87a7002d`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `3dfa766fb1` · 2026-10-07T00:01:00.520508+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 36.5 | 51.4 [48.6, 53.0] | 54.1 [50.3, 55.9] | 9.77 | 10.20 | 2108.5 [960.3, 2284.6] |
| 2 | 0 | 60/60 | 49.4 | 63.6 [60.0, 65.9] | 67.2 [63.0, 69.5] | 14.55 | 15.29 | 1882.9 [902.1, 2663.6] |
| 4 | 0 | 60/60 | 60.9 | 93.1 [75.5, 95.3] | 95.7 [84.9, 96.2] | 16.15 | 17.59 | 1862.5 [990.0, 2247.7] |
| 8 | 0 | 60/60 | 79.3 | 137.8 [110.3, 176.0] | 176.2 [136.8, 176.5] | 18.49 | 21.64 | 2380.7 [1846.0, 2666.5] |
| 16 | 0 | 60/60 | 958.3 | 1477.0 [1279.8, 1517.1] | 1523.6 [1466.5, 1534.3] | 18.62 | 21.90 | 4828.9 [3109.7, 5007.1] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.86 | 96.3 | 1818.9 | 1.86 | 100.0 | 0.0 | 88.5% | 1.2% | 82.8% | 1.04 |
| 2 | 0 | 3.25 | 127.7 | 3160.4 | 3.25 | 100.0 | 0.0 | 88.9% | 1.3% | 87.3% | 1.05 |
| 4 | 0 | 6.12 | 217.5 | 5931.3 | 6.12 | 100.0 | 0.0 | 89.1% | 1.6% | 88.1% | 1.05 |
| 8 | 0 | 7.57 | 320.7 | 7331.9 | 7.57 | 100.0 | 0.0 | 89.2% | 2.1% | 88.2% | 1.05 |
| 16 | 0 | 6.28 | 327.9 | 6113.0 | 0.94 | 15.0 | 0.0 | 88.8% | 2.4% | 87.2% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-8 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
