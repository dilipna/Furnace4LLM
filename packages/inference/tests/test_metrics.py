import numpy as np
import pytest

from furnace_bench.metrics import percentiles, summarize_level, tpot_ms
from furnace_bench.schema import RequestRecord
from furnace_bench.workload_spec import SLO


def test_percentiles_match_numpy_and_ci_brackets_estimate():
    vals = list(range(1, 101))
    p = percentiles(vals)
    assert p.p50 == pytest.approx(np.percentile(vals, 50))
    assert p.p95 == pytest.approx(np.percentile(vals, 95))
    assert p.p99 == pytest.approx(np.percentile(vals, 99))
    assert p.p95_ci is not None
    assert p.p95 is not None
    assert p.p95_ci[0] <= p.p95 <= p.p95_ci[1]


def test_no_ci_for_small_samples_and_empty():
    assert percentiles([1.0, 2.0]).p95_ci is None
    assert percentiles([]).p50 is None


def test_tpot_definition():
    assert tpot_ms(100.0, 1090.0, 100) == pytest.approx(10.0)
    assert tpot_ms(100.0, 200.0, 1) is None
    assert tpot_ms(None, 200.0, 10) is None


def _rec(i, send, ttft, e2e, ok=True, out=11, err=None, slo_ok=None):
    return RequestRecord(
        idx=i,
        level=4,
        ok=ok,
        error=err,
        send_ts=send,
        ttft_ms=ttft,
        e2e_ms=e2e,
        tpot_ms=tpot_ms(ttft, e2e, out) if ok else None,
        input_tokens=100 if ok else None,
        output_tokens=out if ok else None,
        n_chunks=out if ok else 0,
        slo_ok=slo_ok,
    )


def test_summary_window_throughput_goodput_and_failures():
    slo = SLO(ttft_p95_ms=150)
    recs = [
        _rec(0, 0.0, 100, 1000, slo_ok=True),
        _rec(1, 0.5, 200, 1500, slo_ok=False),  # violates TTFT
        _rec(2, 1.0, None, 3000, ok=False, err="total_timeout", slo_ok=False),
        _rec(3, 1.0, 120, 1000, slo_ok=True),
    ]
    s = summarize_level(recs, level=4, repeat=0, slo=slo)
    # window: first send 0.0 -> last completion max(1.0, 2.0, 4.0, 2.0) = 4.0 s
    assert s.window_s == pytest.approx(4.0)
    assert s.n == 4 and s.n_ok == 3
    assert s.request_throughput_rps == pytest.approx(3 / 4.0)
    assert s.slo_goodput_rps == pytest.approx(2 / 4.0)
    assert s.goodput_ratio == pytest.approx(0.5)
    assert s.failure_rate == pytest.approx(0.25)
    assert s.timeout_rate == pytest.approx(0.25)
    assert s.errors == {"total_timeout": 1}
    assert s.output_tok_s == pytest.approx(33 / 4.0)
    assert s.tokens_per_chunk == pytest.approx(1.0)


def test_goodput_absent_without_slo():
    s = summarize_level([_rec(0, 0.0, 100, 1000)], level=1, repeat=0, slo=SLO())
    assert s.slo_goodput_rps is None and s.goodput_ratio is None
