#!/usr/bin/env bash
# Run a Kernel Lab script on the local GPU inside the vLLM image (Linux, CUDA, PyTorch, Triton
# already installed). Usage from the repo root:  bash kernel_lab/run_docker.sh correctness|benchmark
set -euo pipefail
cd "$(dirname "$0")/.."
script="${1:?usage: run_docker.sh correctness|benchmark}"
MSYS_NO_PATHCONV=1 docker run --rm --gpus all --ipc host \
  -e KERNEL_LAB_DATE="${KERNEL_LAB_DATE:-$(date -u +%F)}" \
  -e FURNACE_GIT_SHA="$(git rev-parse HEAD)" \
  -e TRITON_CACHE_DIR=/tmp/triton \
  -v "$(pwd -W 2>/dev/null || pwd)/kernel_lab:/lab" -w /lab \
  --entrypoint python3 vllm/vllm-openai:latest "/lab/${script}.py"
