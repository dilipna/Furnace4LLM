"""NVML GPU sampling (optional dependency: nvidia-ml-py).

Only valid when the benchmark client runs on the same host as the GPU serving
the model; the report records which GPU was sampled so this is never implied
for remote endpoints.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class NVMLSampler:
    def __init__(self, index: int = 0) -> None:
        self.available = False
        self.name: str | None = None
        self.driver: str | None = None
        self._probes: dict[str, Callable[[], float]] = {}
        try:
            import pynvml  # provided by nvidia-ml-py

            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(h)
            self.name = name.decode() if isinstance(name, bytes) else str(name)
            drv = pynvml.nvmlSystemGetDriverVersion()
            self.driver = drv.decode() if isinstance(drv, bytes) else str(drv)
        except Exception:  # no GPU / no NVML library: a normal condition, not an error
            return
        nv: Any = pynvml
        self._probes = {
            "gpu_util_pct": lambda: float(nv.nvmlDeviceGetUtilizationRates(h).gpu),
            "gpu_mem_util_pct": lambda: float(nv.nvmlDeviceGetUtilizationRates(h).memory),
            "gpu_mem_used_mb": lambda: nv.nvmlDeviceGetMemoryInfo(h).used / 2**20,
            "gpu_power_w": lambda: nv.nvmlDeviceGetPowerUsage(h) / 1000.0,
            "gpu_temp_c": lambda: float(nv.nvmlDeviceGetTemperature(h, nv.NVML_TEMPERATURE_GPU)),
            "gpu_sm_clock_mhz": lambda: float(nv.nvmlDeviceGetClockInfo(h, nv.NVML_CLOCK_SM)),
        }
        self.available = True

    def sample(self) -> dict[str, float]:
        """Read every supported metric. A metric the device/driver does not support
        is omitted, so it is reported as not exposed rather than as zero."""
        out: dict[str, float] = {}
        for key, probe in self._probes.items():
            try:
                out[key] = probe()
            except Exception:  # noqa: S112 - unsupported on this device: omit the metric
                continue
        return out
