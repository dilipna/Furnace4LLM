# Kernel Lab: Triton RMSNorm

RMSNorm (`y = x / sqrt(mean(x^2) + eps) * w`) runs before every attention and MLP block in
Qwen2/Llama-family models. It is memory-bound, so it is judged by effective bandwidth against
a measured device copy, not by FLOPs.

| file | what |
|---|---|
| `rmsnorm.py` | fp32 reference, eager PyTorch form (as in Hugging Face Qwen2RMSNorm), Triton kernel (one program per row, fp32 accumulation, single rounding) |
| `correctness.py` | Triton vs fp32 reference for tokens {1, 16, 512, 4096} x hidden {896, 1536, 4096}, fp32/fp16/bf16, at PyTorch's default tolerances; exit 1 on failure |
| `benchmark.py` | eager vs `torch.compile` vs Triton per shape; median times, GB/s, % of measured copy bandwidth, SM clock samples |
| `run_docker.sh` | runs either script on the local GPU inside the `vllm/vllm-openai` image (Linux + CUDA + PyTorch + Triton) |

```bash
uv run poe kernel-correctness     # = bash kernel_lab/run_docker.sh correctness
uv run poe kernel-bench           # = bash kernel_lab/run_docker.sh benchmark
```

Results land in `kernel_lab/results/<UTC date>/{correctness,benchmark}.{json,md}` with the GPU,
library versions and the SM clock observed during the run. On the laptop the GPU clock depends
on the power policy (see `bench/results/2026-10-06/NOTES.md`); compare numbers only at equal
clocks. Do not run this while a FurnaceBench GPU campaign is running.
