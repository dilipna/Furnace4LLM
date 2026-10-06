# furnace-bench report `a8984e519adb`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-on_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1234
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `03c6b6279b` · 2026-10-06T03:33:21.112929+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 34.9 | 49.1 [48.0, 49.3] | 49.4 [48.8, 49.6] | 9.80 | 10.06 | 2092.4 [933.0, 2260.6] |
| 2 | 0 | 60/60 | 47.1 | 61.5 [58.6, 64.3] | 67.8 [60.5, 73.6] | 14.34 | 15.04 | 1794.4 [876.7, 2650.1] |
| 4 | 0 | 60/60 | 60.5 | 86.5 [74.4, 96.3] | 96.4 [84.6, 96.6] | 16.19 | 17.74 | 1865.8 [1028.5, 2242.3] |
| 8 | 0 | 60/60 | 79.4 | 178.1 [131.4, 179.3] | 179.0 [177.6, 179.3] | 19.41 | 21.64 | 2438.5 [1981.4, 2822.3] |
| 16 | 0 | 60/60 | 113.5 | 310.7 [228.2, 311.3] | 311.5 [262.7, 312.0] | 24.35 | 30.07 | 4302.5 [2910.0, 4565.4] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1.87 | 96.8 | 1827.6 | 1.87 | 100.0 | 0.0 | 88.5% | 1.0% | 84.6% | 1.04 |
| 2 | 0 | 3.32 | 130.7 | 3235.5 | 3.32 | 100.0 | 0.0 | 88.7% | 1.1% | 90.1% | 1.05 |
| 4 | 0 | 6.09 | 216.7 | 5909.1 | 6.09 | 100.0 | 0.0 | 89.1% | 1.3% | 89.7% | 1.05 |
| 8 | 0 | 7.43 | 315.0 | 7201.1 | 7.43 | 100.0 | 0.0 | 89.2% | 1.8% | 85.8% | 1.04 |
| 16 | 0 | 8.46 | 441.4 | 8229.0 | 8.46 | 100.0 | 0.0 | 88.8% | 2.9% | 88.9% | 1.03 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-on_seqs-32 repeat=0

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
