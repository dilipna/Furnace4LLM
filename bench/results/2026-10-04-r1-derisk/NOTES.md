# R1 de-risk: shared prompt prefix vs. dynamic head (2026-10-04)

**Question.** Is the planned primary regression (a per-request value prepended to the
system prompt, which defeats prefix caching) measurable on the laptop GPU?

**Setup.** vLLM 0.30.0, Qwen2.5-0.5B-Instruct (served as `lab`), RTX 3050 Ti Laptop
4 GB, `--gpu-memory-utilization 0.70 --max-model-len 4096 --max-num-seqs 32`,
prefix caching on (vLLM default). furnace-bench closed loop, 60 measured + 8 warmup
requests per level, fixed 128 output tokens (`ignore_eos`), streaming, seed 1234/1235.
Both workloads: ~1,720 prompt tokens per request (measured from server usage).

- `21111ede417c` `f1-shape-prefix-stable`: 1,000-token system prompt shared by all requests.
- `91474182777a` `f1-shape-dynamic-head`: no shared prefix (what a dynamic head causes).

**Result (single repeat; p95 with 95% bootstrap CI).**

| c | TTFT p95 stable | TTFT p95 dynamic head | SLO goodput (TTFT ≤ 500 ms) req/s | prefix-cache hit |
|---:|---:|---:|---:|---:|
| 1 | 70 [67, 72] | 119 [117, 120] | 0.95 → 0.91 | 58.7% → 0.9% |
| 4 | 213 [207, 214] | 409 [388, 413] | 3.01 → 2.48 | 58.7% → 0.9% |
| 8 | 374 [341, 397] | 648 [476, 875] | 4.78 → 3.18 | 58.7% → 0.9% |
| 16 | 752 [521, 755] | 1,577 [1,041, 1,712] | 5.83 → 3.01 | 58.7% → 0.9% |

The measured hit rate (58.7%) matches the expected shared fraction (1,000 / ~1,717 = 58.2%).

**Caveats.** One repeat on a laptop GPU (thermal/clock variance not yet characterized);
at c=16 the TTFT *median* is unchanged (369 vs 367 ms) while the tail doubles. The
FurnaceBench RQ4/RQ5 runs will use 3 repeats and report spread.

**Decision.** R1 stays the primary repair scenario.
