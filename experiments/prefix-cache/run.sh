#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
# Prerequisites: Linux/WSL Docker GPU access, uv, cached pinned model/image, AC power.
# HF_HOME_HOST may point to an existing Hugging Face cache. No downloads are automatic.
uv sync --frozen
campaign="${1:-$(date -u +%Y-%m-%dT%H%M%SZ)}"
uv run python experiments/prefix-cache/benchmark.py --campaign "$campaign"
uv run python experiments/prefix-cache/verify.py --campaign "$campaign"
# Rendering dependencies never change the measurement environment.
uv run --with matplotlib==3.10.8 python experiments/prefix-cache/render.py --campaign "$campaign"
