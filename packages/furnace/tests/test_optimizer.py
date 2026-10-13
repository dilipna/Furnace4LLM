import pytest
from furnace.optimizer import (
    ConfigResult,
    OptimizerPolicy,
    confirm,
    confirmation_target,
    paired_diff_ci,
    select,
    welch_ratio_ci,
)

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


# ------------------------------------------------------------------ independent confirmation


def test_confirmation_targets_the_pick_or_the_closest_challenger():
    sel = select([cfg("base", [5, 5.1, 5.2]), cfg("fast", [8, 8.1, 8.2])], "base")
    assert confirmation_target(sel, "base")[0] == "fast"
    sel = select([cfg("base", [9, 9.1, 9.2]), cfg("a", [5, 5.1]), cfg("b", [7, 7.1])], "base")
    assert confirmation_target(sel, "base")[0] == "b"  # the baseline won: test the runner-up
    sel = select([cfg("base", [5, 5.1]), cfg("bad", [9, 9.1], fail=0.5)], "base")
    assert confirmation_target(sel, "base")[0] is None


def test_ratio_interval_is_symmetric_on_the_log_scale():
    ch, lo, hi = welch_ratio_ci([10, 10.5, 9.5, 10], [12, 12.6, 11.4, 12], 0.90)
    assert ch == pytest.approx(20.0, abs=0.3) and lo < ch < hi
    assert (1 + lo / 100) * (1 + hi / 100) == pytest.approx((1 + ch / 100) ** 2, rel=1e-9)


def test_confirm_outcomes():
    base = cfg("base", [5.0, 5.1, 4.9, 5.0])
    assert confirm(base, cfg("c", [8.0, 8.1, 7.9, 8.0]))["outcome"] == "confirmed"
    assert (
        confirm(base, cfg("c", [4.0, 4.1, 3.9, 4.0]))["outcome"] == "not confirmed: no improvement"
    )
    assert confirm(base, cfg("c", [4.0, 6.5, 5.5, 4.5]))["outcome"] == "inconclusive"
    worse = cfg("c", [8.0, 8.1, 7.9, 8.0], quality=qual(1.0, flip=6))  # 30 points lower
    r = confirm(base, worse)
    assert r["outcome"] == "not confirmed: constraints" and "facts" in r["reasons"][0]
    slow = cfg("c", [8.0, 8.1, 7.9, 8.0], p95=900.0)
    assert confirm(base, slow)["outcome"] == "not confirmed: constraints"
    assert confirm(base, cfg("c", [8.0]))["outcome"] == "inconclusive"
    assert confirm(base, cfg("c", [0.0, 8.0]))["outcome"] == "inconclusive"
