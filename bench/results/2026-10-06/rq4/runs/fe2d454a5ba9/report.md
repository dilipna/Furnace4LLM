# furnace-bench report `fe2d454a5ba9`

- **Target:** `vllm` · model `lab` · http://localhost:8101/v1 · pc-off_seqs-32
- **Engine:** vllm 0.30.0 · model root `Qwen/Qwen2.5-0.5B-Instruct`
- **Host:** Windows-11-10.0.26300-SP0 · GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU (driver 592.82)
- **Workload:** `f1-traces`
- **Plan:** closed_loop, levels 1, 2, 4, 8, 16, 60 req/level (+8 warmup), 1 repeat(s), length mode `fixed`, stream=True, seed 1236
- **SLO:** TTFT ≤ 500 ms · TPOT ≤ – ms · E2E ≤ – ms (per request)
- **furnace-bench** 0.1.0 · git `2bf61626a9` · 2026-10-07T00:50:26.585787+00:00

## Latency (ms; p95/p99 with 95% bootstrap CI)

| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 60/60 | 137.5 | 143.3 [140.1, 143.7] | 144.7 [141.7, 146.3] | 9.52 | 9.95 | 1320.2 [529.7, 1897.7] |
| 2 | 0 | 60/60 | 150.9 | 260.3 [160.4, 265.7] | 267.3 [255.1, 270.0] | 15.04 | 21.44 | 1912.3 [1586.5, 2401.8] |
| 4 | 0 | 60/60 | 164.8 | 289.8 [269.0, 403.6] | 441.3 [283.8, 503.2] | 22.79 | 33.08 | 3273.3 [2067.3, 5402.0] |
| 8 | 0 | 60/60 | 172.1 | 656.6 [407.8, 882.4] | 917.2 [642.0, 974.2] | 29.29 | 52.68 | 6376.7 [3650.3, 7295.8] |
| 16 | 0 | 60/60 | 281.8 | 1567.6 [1120.8, 1775.8] | 1786.3 [1516.9, 1803.6] | 50.90 | 70.58 | 7648.9 [4007.9, 7715.7] |

## Throughput, goodput, server

| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 2.14 | 75.9 | 2080.9 | 2.14 | 100.0 | 0.0 | – | 1.0% | 87.1% | 1.05 |
| 2 | 0 | 2.41 | 97.9 | 2335.0 | 2.41 | 100.0 | 0.0 | – | 1.8% | 91.6% | 1.05 |
| 4 | 0 | 3.50 | 148.2 | 3412.5 | 3.44 | 98.3 | 0.0 | – | 3.6% | 92.5% | 1.05 |
| 8 | 0 | 3.97 | 235.4 | 3842.9 | 3.64 | 91.7 | 0.0 | – | 7.0% | 93.7% | 1.03 |
| 16 | 0 | 5.32 | 238.8 | 5165.5 | 3.99 | 75.0 | 0.0 | – | 13.6% | 91.9% | 1.04 |

## Notes

- Prompt lengths calibrated with the server tokenizer (1.000 words/token).
- GPU telemetry from NVML on the benchmark host: NVIDIA GeForce RTX 3050 Ti Laptop GPU. Valid only if the endpoint is served from this host.
- rq4 config=pc-off_seqs-32 repeat=2

## Definitions

- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).
- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.
- **SLO goodput**: successful requests per second that individually met every configured SLO bound, over the window from first send to last completion.
- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.
