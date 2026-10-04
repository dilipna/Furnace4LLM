"""Aggregate per-request records into per-level summaries.

Definitions (all on successful requests unless stated):
- TTFT: send -> first chunk carrying generated output.
- TPOT: (E2E - TTFT) / (output_tokens - 1); undefined for <2 output tokens.
- inter-chunk latency: gaps between output chunks. Reported as *inter-chunk*,
  with the mean tokens-per-chunk, because servers may coalesce tokens.
- throughput: counted over the measurement window = first send -> last completion.
- SLO goodput: requests/s that succeeded AND individually met every configured
  SLO bound, over the same window.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import numpy as np

from furnace_bench.schema import LevelSummary, Percentiles, RequestRecord
from furnace_bench.workload_spec import SLO

TIMEOUT_ERRORS = {"ttft_timeout", "total_timeout"}


def _q(arr: np.ndarray, q: float) -> float:
    return float(np.percentile(arr, q, method="linear"))


def percentiles(
    values: Sequence[float], *, ci: bool = True, n_boot: int = 1000, seed: int = 0
) -> Percentiles:
    """p50/p90/p95/p99 and mean, with percentile-bootstrap 95% CIs for p50/p95/p99.

    CIs are omitted below 20 samples, where a bootstrap of tail percentiles is
    not meaningful.
    """
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return Percentiles()
    out = Percentiles(
        p50=_q(arr, 50),
        p90=_q(arr, 90),
        p95=_q(arr, 95),
        p99=_q(arr, 99),
        mean=float(arr.mean()),
    )
    if ci and arr.size >= 20:
        # Bound memory: n_boot * n floats (<= ~16 MB).
        n_boot = int(max(200, min(n_boot, 2_000_000 // arr.size)))
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
        samples = arr[idx]
        boot = np.percentile(samples, [50, 95, 99], axis=1, method="linear")
        lo = np.percentile(boot, 2.5, axis=1)
        hi = np.percentile(boot, 97.5, axis=1)
        out.p50_ci = (float(lo[0]), float(hi[0]))
        out.p95_ci = (float(lo[1]), float(hi[1]))
        out.p99_ci = (float(lo[2]), float(hi[2]))
    return out


def tpot_ms(ttft_ms: float | None, e2e_ms: float | None, out_tokens: int | None) -> float | None:
    if ttft_ms is None or e2e_ms is None or not out_tokens or out_tokens < 2:
        return None
    return (e2e_ms - ttft_ms) / (out_tokens - 1)


def summarize_level(
    records: Sequence[RequestRecord],
    *,
    level: float,
    repeat: int,
    slo: SLO,
    seed: int = 0,
) -> LevelSummary:
    n = len(records)
    ok = [r for r in records if r.ok]
    errors = Counter(r.error for r in records if not r.ok and r.error)

    if records:
        start = min(r.send_ts for r in records)
        end = max(r.send_ts + (r.e2e_ms or 0.0) / 1000.0 for r in records)
        window = max(end - start, 1e-9)
    else:
        window = 0.0

    def tok_rate(attr: str) -> float | None:
        vals = [getattr(r, attr) for r in ok]
        if not vals or any(v is None for v in vals) or window <= 0:
            return None
        return float(sum(vals)) / window

    in_rate = tok_rate("input_tokens")
    out_rate = tok_rate("output_tokens")

    gaps = [g for r in ok for g in r.chunk_gaps_ms]
    tokens_per_chunk = None
    tok_chunk_pairs = [(r.output_tokens, r.n_chunks) for r in ok if r.output_tokens and r.n_chunks]
    if tok_chunk_pairs:
        tokens_per_chunk = sum(t for t, _ in tok_chunk_pairs) / sum(c for _, c in tok_chunk_pairs)

    good = sum(1 for r in ok if r.slo_ok)
    slo_set = any(v is not None for v in (slo.ttft_p95_ms, slo.tpot_p95_ms, slo.e2e_p95_ms))

    return LevelSummary(
        level=level,
        repeat=repeat,
        n=n,
        n_ok=len(ok),
        window_s=window,
        ttft_ms=percentiles([r.ttft_ms for r in ok if r.ttft_ms is not None], seed=seed),
        tpot_ms=percentiles([r.tpot_ms for r in ok if r.tpot_ms is not None], seed=seed),
        e2e_ms=percentiles([r.e2e_ms for r in ok if r.e2e_ms is not None], seed=seed),
        inter_chunk_ms=percentiles(gaps, ci=False),
        tokens_per_chunk=tokens_per_chunk,
        request_throughput_rps=(len(ok) / window) if window > 0 else 0.0,
        input_tok_s=in_rate,
        output_tok_s=out_rate,
        total_tok_s=(in_rate + out_rate) if in_rate is not None and out_rate is not None else None,
        failure_rate=(n - len(ok)) / n if n else 0.0,
        timeout_rate=sum(errors[e] for e in TIMEOUT_ERRORS) / n if n else 0.0,
        errors=dict(errors),
        slo_goodput_rps=(good / window) if slo_set and window > 0 else None,
        goodput_ratio=(good / n) if slo_set and n else None,
    )
