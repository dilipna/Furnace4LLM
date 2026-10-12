import pytest
from furnace.optimizer import ConfigResult, OptimizerPolicy, paired_diff_ci, select

Q = [f"q{i}" for i in range(20)]


def qual(score: float, flip: int = 0) -> dict[str, dict[str, float]]:
    """Every question at `score`, with the first `flip` questions set to 0."""
    return {"facts": {q: (0.0 if i < flip else score) for i, q in enumerate(Q)}}


def cfg(name, goodput, p95=200.0, fail=0.0, quality=None, error=None):
    return ConfigResult(
        name,
        {},
        goodput_rps=list(goodput),
        ttft_p95_ms=[p95] * len(goodput),
        failure_rate=[fail] * len(goodput),
        quality=quality if quality is not None else qual(1.0),
        launch_error=error,
    )


def test_paired_interval_matches_a_hand_computed_case():
    base = {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0}
    other = {"a": 0.1, "b": 0.0, "c": -0.1, "d": 0.2}  # diffs 10, 0, -10, 20 pts
    m, lo, hi, n = paired_diff_ci(base, other, 0.90)
    sd = 12.909944487358056  # stdev of (10, 0, -10, 20)
    half = 2.3534 * sd / 2  # t(0.95, 3)
    assert (m, n) == (5.0, 4)
    assert lo == pytest.approx(5 - half, abs=1e-3) and hi == pytest.approx(5 + half, abs=1e-3)


def test_highest_goodput_feasible_config_wins():
    res = select([cfg("base", [5, 5.1, 5.2]), cfg("fast", [8, 8.1, 8.2])], "base")
    assert res["pick"] == "fast" and res["ties"] == []
    assert res["recommendation"] == "switch to fast"


def test_overlapping_goodput_with_the_baseline_keeps_the_baseline():
    res = select([cfg("base", [5, 6, 7]), cfg("fast", [6.5, 7.2, 8])], "base")
    assert res["pick"] == "fast" and res["ties"] == ["base"]
    assert res["recommendation"].startswith("keep base")


def test_a_faster_config_that_loses_quality_is_infeasible():
    worse = cfg("small", [9, 9, 9], quality=qual(1.0, flip=6))  # 30 points lost
    res = select([cfg("base", [5, 5, 5]), worse], "base")
    row = next(r for r in res["rows"] if r["name"] == "small")
    assert not row["feasible"] and "worse than the 5-point tolerance" in row["reasons"][0]
    assert res["pick"] == "base"


def test_quality_not_shown_within_tolerance_is_infeasible_not_worse():
    noisy = {"facts": {q: (0.0 if i % 10 == 0 else 1.0) for i, q in enumerate(Q)}}  # -10 pts, noisy
    res = select([cfg("base", [5, 5, 5]), cfg("other", [9, 9, 9], quality=noisy)], "base")
    row = next(r for r in res["rows"] if r["name"] == "other")
    assert not row["feasible"] and "not shown within" in row["reasons"][0]


def test_slo_and_failures_and_launch_errors_exclude_a_config():
    res = select(
        [
            cfg("base", [5, 5, 5]),
            cfg("slow", [9, 9, 9], p95=900.0),
            cfg("flaky", [9, 9, 9], fail=0.05),
            cfg("oom", [], error="CUDA out of memory"),
        ],
        "base",
        OptimizerPolicy(),
    )
    why = {r["name"]: r["reasons"] for r in res["rows"]}
    assert "p95 TTFT 900 ms > SLO 500 ms" in why["slow"][0]
    assert "failure rate 5.0% > 1%" in why["flaky"][0]
    assert "did not launch" in why["oom"][0]
    assert res["pick"] == "base"


def test_pareto_front_marks_dominated_configs():
    res = select([cfg("base", [5, 5, 5], p95=300.0), cfg("better", [6, 6, 6], p95=200.0)], "base")
    pareto = {r["name"]: r["pareto"] for r in res["rows"]}
    assert pareto == {"base": False, "better": True}


def test_baseline_must_have_been_measured():
    with pytest.raises(ValueError):
        select([cfg("base", [], error="failed")], "base")
