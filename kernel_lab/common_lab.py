"""Environment manifest and output directory for Kernel Lab runs."""

from __future__ import annotations

import datetime as dt
import os
import platform
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parent


def out_dir() -> Path:
    date = os.environ.get("KERNEL_LAB_DATE") or dt.datetime.now(dt.UTC).date().isoformat()
    d = ROOT / "results" / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def sm_clock_mhz() -> float | None:
    """Current SM clock via NVML when available (the laptop GPU's clock is not fixed)."""
    try:
        import pynvml

        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(torch.cuda.current_device())
        return float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM))
    except Exception:
        return None


def env() -> dict[str, Any]:
    try:
        import triton

        triton_version = triton.__version__
    except ImportError:
        triton_version = None
    p = torch.cuda.get_device_properties(0)
    return {
        "gpu": p.name,
        "sm": f"{p.major}.{p.minor}",
        "memory_mb": p.total_memory // 2**20,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "triton": triton_version,
        "python": platform.python_version(),
        "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "sm_clock_mhz_at_start": sm_clock_mhz(),
        "furnace_git_sha": os.environ.get("FURNACE_GIT_SHA"),
    }
