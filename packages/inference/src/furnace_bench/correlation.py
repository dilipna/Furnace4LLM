"""TTFT versus server queue state: join each request with the telemetry at its send time.

Requests and telemetry samples share the runner's `perf_counter` origin (`send_ts` and `t`
are seconds since the run started), so each request is matched with the last telemetry
sample at or before it was sent. Spearman's rank correlation (ties get average ranks) is
computed per concurrency level: pooling levels would mostly measure that higher
concurrency raises both the queue and TTFT. Requests within a run are not independent, so
rho is descriptive; no p-value is attached.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np


def _ranks(x: Sequence[float]) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[order[j + 1]] == a[order[i]]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1  # average rank for ties
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Spearman's rho with average ranks for ties; None if either side is constant or n < 3."""
    if len(x) != len(y):
        raise ValueError("x and y differ in length")
    if len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def state_at_send(
    requests: Iterable[dict[str, Any]], telemetry: Sequence[dict[str, Any]], field: str
) -> list[tuple[float, float, float]]:
    """(level, telemetry[field] at send, ttft_ms) for every successful request that has a
    telemetry sample at or before its send time and a non-null value."""
    ts = [float(s["t"]) for s in telemetry]
    out = []
    for r in requests:
        if not r.get("ok") or r.get("ttft_ms") is None:
            continue
        i = bisect.bisect_right(ts, float(r["send_ts"])) - 1
        if i < 0:
            continue
        v = telemetry[i].get(field)
        if v is None:
            continue
        out.append((float(r["level"]), float(v), float(r["ttft_ms"])))
    return out


def by_level(
    requests: Iterable[dict[str, Any]], telemetry: Sequence[dict[str, Any]], field: str
) -> dict[float, dict[str, Any]]:
    rows = state_at_send(requests, telemetry, field)
    out: dict[float, dict[str, Any]] = {}
    for lvl in sorted({r[0] for r in rows}):
        xs = [r[1] for r in rows if r[0] == lvl]
        ys = [r[2] for r in rows if r[0] == lvl]
        out[lvl] = {"n": len(xs), "rho": spearman(xs, ys), "state_max": max(xs)}
    return out
