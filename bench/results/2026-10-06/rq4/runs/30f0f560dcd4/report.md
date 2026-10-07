# furnace-bench report `30f0f560dcd4`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-8
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1235
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `0b2f3cb36b` · 2026-10-07T00:40:25.602807+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 35.1 | 49.2 [47.3, 50.1] | 50.3 [48.9, 50.6] | 9.90 | 10.24 | 1051.1 [594.3, 1647.4] |
| 2 | 0 | 60/60 | 48.2 | 70.8 [62.1, 75.0] | 75.2 [69.8, 75.4] | 14.61 | 15.15 | 3043.1 [1466.8, 3344.2] |
| 4 | 0 | 60/60 | 61.9 | 86.4 [76.8, 111.5] | 111.7 [81.8, 112.0] | 15.95 | 17.94 | 3155.2 [1577.8, 3709.6] |
| 8 | 0 | 60/60 | 82.8 | 154.3 [113.5, 155.0] | 155.0 [153.9, 155.0] | 19.84 | 22.04 | 2451.7 [1281.7, 2793.8] |
| 16 | 0 | 60/60 | 747.8 | 1016.0 [921.2, 1025.7] | 1035.4 [990.7, 1051.3] | 19.56 | 22.95 | 2521.5 [1803.2, 3588.6] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.66 | 93.9 | 2576.3 | 2.66 | 100.0 | 0.0 | 89.3% | 1.2% | 82.4% | 1.04 |
| 2 | 0 | 2.63 | 128.1 | 2583.5 | 2.63 | 100.0 | 0.0 | 88.1% | 1.5% | 87.7% | 1.03 |
| 4 | 0 | 4.33 | 213.2 | 4226.6 | 4.33 | 100.0 | 0.0 | 88.5% | 1.7% | 88.2% | 1.03 |
| 8 | 0 | 8.84 | 323.8 | 8610.2 | 8.84 | 100.0 | 0.0 | 88.7% | 2.1% | 88.1% | 1.03 |
| 16 | 0 | 7.76 | 298.0 | 7558.5 | 1.29 | 16.7 | 0.0 | 88.7% | 2.2% | 89.5% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-8 repeat=1

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
