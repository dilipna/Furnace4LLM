# RQ4: inference sweep on W1 (F1 trace fingerprint)

Hardware: NVIDIA GeForce RTX 3050 Ti Laptop GPU (4096 MB), driver 592.82. Engine: vllm 0.30.0, image `vllm/vllm-openai@sha256:8a69ffad015f138d7170c4ddc429e230a3bc1c1719f67e14324749df200a4b90`, model Qwen/Qwen2.5-0.5B-Instruct. Furnace commit `3dfa766fb153d3e7dca48ba4255d1256c0b70b64`.

Workload: `bench/results/2026-10-04-f1-quality/workload-f1-traces-qwen05b.yaml`, mean 963 input tokens of which 857 are a shared system prefix; output lengths sampled from the trace distribution (fixed per request, `ignore_eos`). Closed loop, 60 measured + 8 warmup requests per level, SLO TTFT <= 500 ms.

Cells: median across repeats [min, max]. Each repeat is a fresh server launch.

Caveats: one laptop GPU (thermals and clocks not pinned; max GPU temperature per level is in `rq4.json`). The host was not idle: development work (editor, linters, a few short Docker sandbox test runs) continued during the sweep, which can add client-side and scheduling noise. Repeats are interleaved so such noise spreads across configs rather than biasing one.

## TTFT p95 (ms) by config and concurrency

| config | c=1 | c=2 | c=4 | c=8 | c=16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pc-off_seqs-128 | 140 [140, 143] | 261 [256, 265] | 285 [282, 380] | 656 [650, 662] | 1,547 [1,541, 1,549] |
| pc-off_seqs-32 | 143 [142, 145] | 260 [258, 262] | 293 [290, 387] | 652 [641, 657] | 1,568 [1,539, 1,568] |
| pc-off_seqs-8 | 140 [139, 142] | 263 [259, 266] | 384 [289, 388] | 655 [648, 656] | 2,244 [1,987, 2,435] |
| pc-on_seqs-128 | 50 [48, 50] | 64 [63, 65] | 89 [83, 89] | 158 [140, 164] | 303 [299, 313] |
| pc-on_seqs-32 | 49 [47, 52] | 64 [63, 66] | 87 [81, 94] | 159 [156, 169] | 294 [253, 310] |
| pc-on_seqs-8 | 49 [48, 51] | 64 [63, 71] | 86 [86, 93] | 154 [138, 167] | 1,137 [1,016, 1,477] |

## SLO goodput (req/s)

| config | c=1 | c=2 | c=4 | c=8 | c=16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pc-off_seqs-128 | 2.10 [1.61, 2.13] | 2.44 [2.08, 2.45] | 3.50 [3.07, 3.65] | 4.00 [3.55, 4.46] | 4.62 [4.14, 4.69] |
| pc-off_seqs-32 | 2.12 [1.56, 2.14] | 2.41 [2.09, 2.43] | 3.44 [2.99, 3.66] | 3.90 [3.64, 4.46] | 4.20 [3.99, 4.21] |
| pc-off_seqs-8 | 2.13 [1.61, 2.15] | 2.39 [2.10, 2.42] | 3.47 [2.99, 3.71] | 3.98 [3.52, 4.75] | 0.22 [0.19, 0.24] |
| pc-on_seqs-128 | 2.67 [1.86, 2.73] | 3.10 [2.65, 3.29] | 5.33 [4.27, 6.12] | 7.63 [6.18, 8.72] | 9.27 [8.42, 9.33] |
| pc-on_seqs-32 | 2.70 [1.85, 2.75] | 3.13 [2.61, 3.29] | 5.56 [4.29, 6.11] | 7.66 [6.38, 8.76] | 9.41 [8.51, 9.50] |
| pc-on_seqs-8 | 2.66 [1.86, 2.75] | 3.25 [2.63, 3.32] | 5.48 [4.33, 6.12] | 7.57 [6.37, 8.84] | 1.02 [0.94, 1.29] |

## Output throughput (tok/s)

| config | c=1 | c=2 | c=4 | c=8 | c=16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pc-off_seqs-128 | 76 [74, 83] | 99 [96, 101] | 148 [132, 151] | 185 [178, 229] | 265 [230, 288] |
| pc-off_seqs-32 | 76 [75, 81] | 98 [95, 102] | 148 [132, 150] | 183 [178, 235] | 239 [220, 281] |
| pc-off_seqs-8 | 77 [75, 83] | 97 [95, 102] | 149 [134, 150] | 190 [184, 228] | 194 [188, 203] |
| pc-on_seqs-128 | 96 [95, 96] | 129 [126, 129] | 218 [210, 226] | 323 [319, 366] | 419 [356, 439] |
| pc-on_seqs-32 | 96 [95, 97] | 127 [127, 129] | 217 [211, 235] | 325 [321, 378] | 427 [361, 444] |
| pc-on_seqs-8 | 96 [94, 98] | 128 [128, 135] | 218 [213, 232] | 324 [321, 377] | 328 [298, 343] |

## TPOT p50 (ms)

| config | c=1 | c=2 | c=4 | c=8 | c=16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pc-off_seqs-128 | 9.6 [9.5, 9.9] | 16.0 [14.5, 16.4] | 22.6 [21.3, 24.2] | 34.5 [30.4, 35.2] | 45.1 [40.7, 49.0] |
| pc-off_seqs-32 | 9.7 [9.5, 9.8] | 15.2 [15.0, 16.1] | 22.8 [21.6, 24.1] | 34.8 [29.3, 36.3] | 50.9 [44.0, 54.1] |
| pc-off_seqs-8 | 9.5 [9.4, 9.6] | 15.6 [14.8, 15.8] | 22.6 [21.4, 23.5] | 34.1 [30.1, 34.9] | 32.1 [31.7, 33.1] |
| pc-on_seqs-128 | 9.7 [9.6, 9.7] | 14.5 [14.5, 14.9] | 16.2 [16.2, 16.3] | 18.5 [18.5, 19.6] | 26.2 [24.9, 27.7] |
| pc-on_seqs-32 | 9.6 [9.5, 9.9] | 14.6 [14.4, 14.7] | 16.1 [15.7, 16.1] | 18.6 [18.0, 19.8] | 26.1 [24.6, 27.9] |
| pc-on_seqs-8 | 9.8 [9.4, 9.9] | 14.6 [14.5, 14.6] | 16.0 [15.9, 16.2] | 18.5 [17.9, 19.8] | 19.0 [18.6, 19.6] |

## Prefix-cache hit rate (%)

| config | c=1 | c=2 | c=4 | c=8 | c=16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pc-off_seqs-128 | – | – | – | – | – |
| pc-off_seqs-32 | – | – | – | – | – |
| pc-off_seqs-8 | – | – | – | – | – |
| pc-on_seqs-128 | 88.7 [88.5, 89.3] | 88.7 [88.1, 89.1] | 88.7 [88.5, 89.1] | 89.2 [88.7, 89.3] | 88.8 [88.7, 88.9] |
| pc-on_seqs-32 | 88.7 [88.5, 89.3] | 88.9 [88.1, 89.1] | 88.7 [88.5, 89.1] | 89.2 [88.7, 89.3] | 88.8 [88.7, 88.9] |
| pc-on_seqs-8 | 88.7 [88.5, 89.3] | 88.9 [88.1, 89.1] | 88.7 [88.5, 89.1] | 89.2 [88.7, 89.3] | 88.8 [88.7, 88.9] |

## Failure rate (%)

| config | c=1 | c=2 | c=4 | c=8 | c=16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pc-off_seqs-128 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| pc-off_seqs-32 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| pc-off_seqs-8 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| pc-on_seqs-128 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| pc-on_seqs-32 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| pc-on_seqs-8 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |

## Paired prefix-cache effect (same seed per repeat; off vs on)

| max-num-seqs | c | pairs | TTFT p95 change when off (%) | goodput lost when off (req/s) | same sign in every pair |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 | 1 | 3 | 184.4 [176.1, 187.3] | 0.53 [0.25, 0.59] | yes |
| 8 | 2 | 3 | 313.9 [265.2, 322.7] | 0.82 [0.53, 0.92] | yes |
| 8 | 4 | 3 | 317.0 [237.4, 344.2] | 2.01 [1.34, 2.40] | yes |
| 8 | 8 | 3 | 319.8 [291.6, 376.0] | 3.59 [2.84, 4.10] | yes |
| 8 | 16 | 3 | 95.6 [64.8, 97.4] | 0.80 [0.75, 1.05] | yes |
| 32 | 1 | 3 | 193.1 [179.0, 201.2] | 0.57 [0.28, 0.63] | yes |
| 32 | 2 | 3 | 304.0 [296.3, 314.4] | 0.72 [0.52, 0.86] | yes |
| 32 | 4 | 3 | 260.7 [234.3, 310.6] | 2.11 [1.30, 2.46] | yes |
| 32 | 8 | 3 | 303.6 [287.9, 319.0] | 3.76 [2.74, 4.30] | yes |
| 32 | 16 | 3 | 432.7 [395.9, 520.5] | 5.21 [4.30, 5.51] | yes |
| 128 | 1 | 3 | 180.7 [177.1, 196.5] | 0.53 [0.25, 0.64] | yes |
| 128 | 2 | 3 | 309.8 [303.5, 312.7] | 0.66 [0.57, 0.85] | yes |
| 128 | 4 | 3 | 241.1 [216.4, 329.6] | 1.83 [1.20, 2.48] | yes |
| 128 | 8 | 3 | 312.0 [300.9, 371.8] | 3.63 [2.63, 4.26] | yes |
| 128 | 16 | 3 | 411.8 [394.7, 416.2] | 4.58 [4.28, 4.71] | yes |

Simulated vs measured reuse: the workload's shared prefix predicts a hit rate of 89.0% (prefix tokens / mean input tokens; the F1 trace replay estimated 93.5%). Measured vLLM hit rates are in the table above.

## GPU state during the sweep

Mean SM clock per run: 780–830 MHz (spread 6.0%); max power 64 W; max temperature 61 °C; all runs on AC: yes.

Config comparisons inside one sweep assume a steady clock (small spread above). Absolute latencies depend on the clock the laptop allowed; compare them across days only at equal clocks (see NOTES.md in this directory for the conditions of this campaign).
