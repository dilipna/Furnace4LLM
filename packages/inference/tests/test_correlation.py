import pytest

from furnace_bench.correlation import by_level, spearman, state_at_send


def test_spearman_known_values_and_ties():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    # ties: ranks x = (1.5, 1.5, 3, 4), y = (1, 2, 3, 4) -> Pearson on ranks
    assert spearman([0, 0, 1, 2], [1, 2, 3, 4]) == pytest.approx(0.9486833, abs=1e-6)


def test_spearman_undefined_cases():
    assert spearman([0, 0, 0], [1, 2, 3]) is None  # constant queue: no correlation to report
    assert spearman([1, 2], [1, 2]) is None
    with pytest.raises(ValueError):
        spearman([1, 2, 3], [1, 2])


def test_requests_take_the_last_sample_at_or_before_send():
    tel = [{"t": 0.0, "waiting": 0}, {"t": 1.0, "waiting": 3}, {"t": 2.0, "waiting": None}]
    reqs = [
        {"ok": True, "level": 8, "send_ts": 0.5, "ttft_ms": 50},  # sample t=0.0
        {"ok": True, "level": 8, "send_ts": 1.0, "ttft_ms": 90},  # exactly at t=1.0
        {"ok": True, "level": 8, "send_ts": 2.5, "ttft_ms": 99},  # null value: dropped
        {"ok": False, "level": 8, "send_ts": 1.5, "ttft_ms": None},  # failed: dropped
        {"ok": True, "level": 8, "send_ts": -0.1, "ttft_ms": 10},  # before telemetry: dropped
    ]
    assert state_at_send(reqs, tel, "waiting") == [(8.0, 0.0, 50.0), (8.0, 3.0, 90.0)]


def test_levels_are_not_pooled():
    tel = [{"t": 0.0, "waiting": 0}, {"t": 10.0, "waiting": 5}]
    reqs = [{"ok": True, "level": 1, "send_ts": 1 + i * 0.1, "ttft_ms": 30 + i} for i in range(5)]
    reqs += [
        {"ok": True, "level": 16, "send_ts": 11 + i * 0.1, "ttft_ms": 300 + i} for i in range(5)
    ]
    res = by_level(reqs, tel, "waiting")
    assert set(res) == {1.0, 16.0}
    assert res[1.0]["rho"] is None and res[16.0]["rho"] is None  # constant queue inside each level
