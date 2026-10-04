"""Background telemetry sampling and per-window aggregation.

Samples are (t, metrics) with t in seconds relative to the run start, on the
same clock as request send timestamps, so they can be joined to requests.

Canonical metric names:
  gauges   : running, waiting, kv_cache_usage, gpu_util_pct, gpu_mem_used_mb,
             gpu_power_w, gpu_temp_c, gpu_sm_clock_mhz
  counters : prefix_cache_queries, prefix_cache_hits
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from furnace_bench.telemetry.nvml import NVMLSampler

COUNTERS = ("prefix_cache_queries", "prefix_cache_hits")
GAUGES = (
    "running",
    "waiting",
    "kv_cache_usage",
    "gpu_util_pct",
    "gpu_mem_used_mb",
    "gpu_power_w",
    "gpu_temp_c",
    "gpu_sm_clock_mhz",
)


@dataclass
class Sample:
    t: float
    metrics: dict[str, float]


@dataclass
class TelemetryCollector:
    t0: float  # perf_counter at run start
    scrape: Callable[[], Awaitable[dict[str, float]]] | None
    nvml: NVMLSampler | None
    interval_s: float = 0.25
    samples: list[Sample] = field(default_factory=list)
    _task: asyncio.Task[None] | None = None

    async def _loop(self) -> None:
        while True:
            t = time.perf_counter() - self.t0
            metrics: dict[str, float] = {}
            if self.scrape is not None:
                with contextlib.suppress(Exception):
                    metrics.update(await self.scrape())
            if self.nvml is not None and self.nvml.available:
                metrics.update(self.nvml.sample())
            if metrics:
                self.samples.append(Sample(t, metrics))
            await asyncio.sleep(self.interval_s)

    def start(self) -> None:
        if self.scrape is None and (self.nvml is None or not self.nvml.available):
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def aggregate(self, start: float, end: float) -> tuple[dict[str, float], list[str]]:
        """Aggregate samples within [start, end]. Returns (telemetry, not_exposed)."""
        inside = [s for s in self.samples if start <= s.t <= end]
        seen: set[str] = {k for s in self.samples for k in s.metrics}
        out: dict[str, float] = {}
        for g in GAUGES:
            vals = [s.metrics[g] for s in inside if g in s.metrics]
            if vals:
                out[f"{g}_mean"] = sum(vals) / len(vals)
                out[f"{g}_max"] = max(vals)

        def counter_at(name: str, t: float) -> float | None:
            prior = [s.metrics[name] for s in self.samples if s.t <= t and name in s.metrics]
            return prior[-1] if prior else None

        deltas: dict[str, float] = {}
        for c in COUNTERS:
            a, b = counter_at(c, start), counter_at(c, end)
            if a is not None and b is not None:
                deltas[c] = b - a
        if deltas.get("prefix_cache_queries"):
            out["prefix_cache_hit_rate"] = (
                deltas.get("prefix_cache_hits", 0.0) / deltas["prefix_cache_queries"]
            )
            out["prefix_cache_queries_delta"] = deltas["prefix_cache_queries"]
        not_exposed = [m for m in (*GAUGES, *COUNTERS) if m not in seen]
        return out, not_exposed
