import pytest
from furnace.guardian.execute import ItemResult, fisher_one_sided_less, verdict
from furnace.guardian.perf_gate import GatePolicy, compare


def test_fisher_matches_known_values():
    assert fisher_one_sided_less(2, 34, 5, 34) == pytest.approx(0.2135, abs=1e-3)
    assert fisher_one_sided_less(5, 34, 20, 34) < 0.001
    assert fisher_one_sided_less(5, 34, 5, 34) > 0.5
    assert fisher_one_sided_less(0, 10, 0, 10) == pytest.approx(1.0)


class _R:
    def __init__(self, p95):
        self.p95 = p95

    def metric(self, name):
        return {"ttft_p95_ms": self.p95, "prefix_hit_rate": 0.9, "goodput_rps": 5.0}[name]


def runs(*xs):
    return [_R(x) for x in xs]


def test_summary_only_comparisons_are_diagnostic_not_decisions():
    pol = GatePolicy()
    c = compare(runs(600, 620, 610), runs(1500, 1480, 1520), pol)
    assert c["verdict"] == "inconclusive" and c["separated"]
    noisy = compare(runs(300, 600, 450), runs(420, 900, 500), pol)  # +11% median, overlapping
    assert noisy["verdict"] == "inconclusive" and not noisy["separated"]
    big_overlap = compare(
        runs(300, 900, 400), runs(800, 350, 700), pol
    )  # +75% median but overlapping
    assert big_overlap["verdict"] == "inconclusive"
    assert compare(runs(500, 510), runs(505, 495), pol)["verdict"] == "inconclusive"


def test_single_summary_cannot_establish_a_latency_regression():
    assert compare(runs(500), runs(700), GatePolicy())["verdict"] == "inconclusive"


def test_conclusion_mapping():
    r = lambda v: ItemResult("k", v, "")  # noqa: E731
    assert verdict([r("pass"), r("skip")]) == "success"
    assert verdict([r("pass"), r("warn")]) == "neutral"
    assert verdict([r("error")]) == "neutral"
    assert verdict([r("warn"), r("fail")]) == "failure"


# ------------------------------------------------- interval-based decisions (real gate path)

import numpy as np  # noqa: E402
from furnace.guardian.perf_gate import (  # noqa: E402
    METHOD_POINT,
    accept_repair,
    repair_perf_check,
    run_order,
    welch_change_ci,
)


class _S:
    """A run with per-request TTFT samples, like perf_gate.VariantResult."""

    def __init__(self, xs):
        self.xs = list(xs)

    def samples(self, name):
        return self.xs if name == "ttft_ms" else []

    def metric(self, name):
        if name == "ttft_p95_ms":
            return float(np.percentile(self.xs, 95))
        return {"prefix_hit_rate": 0.9, "goodput_rps": 5.0}[name]


def sruns(scale=1.0, n=34, k=3, spread=0.12, seed=0, jitter=0.0):
    rng = np.random.default_rng(seed)
    return [
        _S(np.exp(rng.normal(np.log(80), spread, n)) * scale * (1 + jitter * (i - 1)))
        for i in range(k)
    ]


def test_identical_tight_runs_pass_with_an_interval():
    c = compare(sruns(seed=1, n=200, spread=0.03), sruns(seed=2, n=200, spread=0.03), GatePolicy())
    assert "Welch" in c["method"] and c["verdict"] == "pass"
    lo, hi = c["ci_pct"]
    assert lo <= 0 <= hi and hi <= 10
    assert len(c["samples_ms"]["baseline"]) == 3 and len(c["samples_ms"]["value"][0]) == 200


def test_large_separated_regression_blocks():
    c = compare(sruns(seed=1), sruns(scale=10, seed=2), GatePolicy())
    assert c["verdict"] == "block" and c["ci_pct"][0] > 10 and c["separated"]
    assert c["metric"] == "ttft_gmean_ms" and c["confidence"] == 0.90


def test_confident_but_small_regression_warns():
    c = compare(
        sruns(seed=1, n=300, spread=0.02), sruns(1.18, seed=2, n=300, spread=0.02), GatePolicy()
    )
    assert c["verdict"] == "warn" and c["ci_pct"][0] > 10 and c["change_pct"] < 25


def test_noise_that_straddles_the_tolerance_is_inconclusive_not_pass():
    c = compare(sruns(seed=1, spread=0.3), sruns(1.08, seed=2, spread=0.3), GatePolicy())
    lo, hi = c["ci_pct"]
    assert lo <= 10 < hi and c["verdict"] == "inconclusive"


def test_summaries_without_samples_are_labeled_diagnostic_only():
    c = compare(runs(600, 620, 610), runs(1500, 1480, 1520), GatePolicy())
    assert c["method"] == METHOD_POINT and c["ci_pct"] is None


def test_welch_interval_matches_a_hand_computed_case():
    # d = 0.1; se = sqrt(0.01/3 + 0.01/3); Satterthwaite df = 4; t(0.95, 4) = 2.1318
    change, lo, hi = welch_change_ci([0.0, 0.1, -0.1], [0.1, 0.2, 0.0], 0.90)
    half = 2.1318 * (0.02 / 3) ** 0.5
    assert change == pytest.approx((np.exp(0.1) - 1) * 100, abs=1e-6)
    assert lo == pytest.approx((np.exp(0.1 - half) - 1) * 100, abs=0.02)
    assert hi == pytest.approx((np.exp(0.1 + half) - 1) * 100, abs=0.02)


def test_the_run_is_the_unit_not_the_request():
    """Run-to-run variation sets the interval: 100x more requests per run must not shrink it
    to nothing (a request-level resample would), because requests within a run are dependent
    and the runs differ by their own offsets."""

    def offset_runs(n, factors):
        rng = np.random.default_rng(5)
        return [_S(np.exp(rng.normal(np.log(80), 0.02, n)) * f) for f in factors]

    few = compare(
        offset_runs(34, (0.9, 1.0, 1.1)), offset_runs(34, (0.95, 1.05, 1.15)), GatePolicy()
    )
    many = compare(
        offset_runs(3400, (0.9, 1.0, 1.1)), offset_runs(3400, (0.95, 1.05, 1.15)), GatePolicy()
    )
    w = lambda c: c["ci_pct"][1] - c["ci_pct"][0]  # noqa: E731
    assert w(many) > 0.8 * w(few)
    assert many["verdict"] == "inconclusive"  # +5% with +-10% run offsets cannot be settled


def test_fewer_than_three_runs_per_side_is_inconclusive_not_a_verdict():
    c = compare(sruns(seed=1, k=2), sruns(scale=10, seed=2, k=2), GatePolicy())
    assert c["verdict"] == "inconclusive" and c["ci_pct"] is None
    assert "at least 3 per side" in c["reason"]


def test_a_tail_only_regression_is_reported_in_p95_but_does_not_decide():
    """The documented limit of the geometric-mean gate (docs/gate-revision.md): slow the
    slowest 6% of requests 3x and leave the rest alone. The p95 shows it; the verdict, which
    is on the geometric mean, does not."""

    def tail_slowed(seed, factor):
        out = []
        for r in sruns(seed=seed, n=100, spread=0.02):
            xs = np.sort(r.xs)
            xs[-6:] *= factor
            out.append(_S(xs))
        return out

    c = compare(tail_slowed(1, 1.0), tail_slowed(2, 3.0), GatePolicy())
    assert c["p95_advisory"]["ci_pct"][0] > 100
    assert c["verdict"] == "pass" and c["change_pct"] < 10


def test_the_gate_is_deterministic():
    a, b = sruns(seed=3), sruns(1.05, seed=4)
    assert compare(a, b, GatePolicy()) == compare(a, b, GatePolicy())


def _cmp(change, lo, hi, verdict="pass"):
    return {"change_pct": change, "ci_pct": [lo, hi], "verdict": verdict}


def test_repair_accepted_only_if_faster_than_head_and_bounded_against_base():
    pol = GatePolicy()
    head = _cmp(900, 700, 1100, "block")
    ok, why = accept_repair(head, _cmp(3, -6, 12, "inconclusive"), _cmp(-90, -92, -88), pol)
    assert ok and any("NOT shown" in w for w in why)  # within tolerance not shown: reported
    ok, _ = accept_repair(head, _cmp(2, -5, 8), _cmp(-1, -9, 6), pol)
    assert not ok  # not shown faster than the PR head: not a repair
    ok, why = accept_repair(head, _cmp(40, 30, 50, "warn"), _cmp(-85, -88, -80), pol)
    assert not ok and any(">= block threshold" in w for w in why)  # a new regression
    ok, _ = accept_repair({"verdict": "error"}, _cmp(0, -1, 1), _cmp(-90, -92, -88), pol)
    assert not ok


def test_run_order_rotates_so_no_revision_is_always_first():
    names = ["base", "pr_head", "candidate"]
    orders = [run_order(names, r) for r in range(3)]
    assert [o[0] for o in orders] == ["base", "pr_head", "candidate"]
    assert all(sorted(o) == sorted(names) for o in orders)
    assert run_order(["a", "b"], 1) == ["b", "a"]


def test_inconclusive_is_never_a_successful_check():
    r = lambda v: ItemResult("k", v, "")  # noqa: E731
    # execute._bench maps an INCONCLUSIVE gate to an item verdict of warn -> neutral check
    assert verdict([r("pass"), r("warn")]) == "neutral"


class _F(_S):
    """A run that also reports its failed-request share, like VariantResult."""

    def __init__(self, xs, failure_rate):
        super().__init__(xs)
        self.fr = failure_rate

    def metric(self, name):
        return self.fr if name == "failure_rate" else super().metric(name)


def test_a_faster_revision_whose_requests_fail_is_blocked_not_passed():
    """Audit 2026-10-12: latency is measured over successful requests only, so failures
    used to be invisible to the gate; a candidate failing 20% of requests looked fine."""
    base = [_F(r.xs, 0.0) for r in sruns(seed=1, n=200, spread=0.03)]
    fast_but_failing = [_F(r.xs, 0.2) for r in sruns(0.9, seed=2, n=200, spread=0.03)]
    c = compare(base, fast_but_failing, GatePolicy())
    assert c["verdict"] == "block" and "20% of requests failed" in c["reason"]
    assert c["failure_rate"] == (0.0, 0.2)
    ok, why = accept_repair(_cmp(900, 700, 1100, "block"), c, _cmp(-90, -92, -88), GatePolicy())
    assert not ok and "requests failed" in why[0]
    # one transient failure in a hundred is within the allowance
    one_off = [_F(r.xs, 0.01) for r in sruns(seed=3, n=200, spread=0.03)]
    assert compare(base, one_off, GatePolicy())["verdict"] == "pass"


@pytest.mark.parametrize("n", [1, 19])
def test_insufficient_samples_cannot_fall_back_to_a_pass(n):
    c = compare(sruns(n=n), sruns(n=n), GatePolicy())
    assert c["verdict"] == "inconclusive"
    assert c["ci_pct"] is None
    assert "20" in c["reason"]


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_sample_cannot_fall_back_to_a_pass(bad):
    base, head = sruns(), sruns()
    head[1].xs[0] = bad
    c = compare(base, head, GatePolicy())
    assert c["verdict"] in ("inconclusive", "error")
    assert c.get("ci_pct") is None


def test_one_incomplete_run_invalidates_the_comparison():
    base, head = sruns(), sruns()
    head[1] = _S([80.0] * 19)
    assert compare(base, head, GatePolicy())["verdict"] == "inconclusive"


def test_summary_only_repair_is_rejected_even_when_within_point_budget():
    pol = GatePolicy()
    ok, why = accept_repair(
        compare(runs(100), runs(110), pol),
        compare(runs(100), runs(120), pol),
        compare(runs(110), runs(120), pol),
        pol,
    )
    assert not ok
    assert any("interval" in reason for reason in why)


@pytest.mark.parametrize("missing", ["base", "head"])
def test_repair_requires_both_candidate_intervals(missing):
    base, head = _cmp(0, -1, 1), _cmp(-50, -60, -40)
    (base if missing == "base" else head)["ci_pct"] = None
    ok, _ = accept_repair(_cmp(100, 90, 110, "block"), base, head, GatePolicy())
    assert not ok


@pytest.mark.parametrize("ci", [[-2, float("inf")], [float("nan"), -1], [1, -1], []])
def test_repair_rejects_invalid_intervals(ci):
    head = _cmp(-50, -60, -40)
    head["ci_pct"] = ci
    ok, _ = accept_repair(_cmp(100, 90, 110, "block"), _cmp(0, -1, 1), head, GatePolicy())
    assert not ok


def test_repair_rejects_error_in_candidate_vs_head():
    head = _cmp(-50, -60, -40, "error")
    ok, _ = accept_repair(_cmp(100, 90, 110, "block"), _cmp(0, -1, 1), head, GatePolicy())
    assert not ok


def test_failure_increase_still_blocks_with_insufficient_timing_samples():
    base = [_F([100.0] * 19, 0.0)]
    head = [_F([80.0] * 19, 0.2)]
    c = compare(base, head, GatePolicy())
    assert c["verdict"] == "block"
    assert "20% of requests failed" in c["reason"]


@pytest.mark.parametrize("summary", [None, 0.0, -1.0, float("nan"), float("inf")])
def test_missing_or_invalid_summary_is_not_dropped(summary):
    c = compare(runs(100, 100, 100), runs(100, summary, 100), GatePolicy())
    assert c["verdict"] == "error"


def test_all_failed_requests_block_even_without_latency_summary():
    c = compare([_F([100.0] * 34, 0.0)], [_F([], 1.0)], GatePolicy())
    assert c["verdict"] == "block"
    assert "100% of requests failed" in c["reason"]


def test_empty_samples_are_reported_without_percentile_crash():
    c = compare(sruns(n=0), sruns(n=0), GatePolicy())
    assert c["verdict"] == "error"


def test_minimum_valid_sample_count_still_uses_interval():
    c = compare(sruns(n=20, spread=0.01), sruns(n=20, spread=0.01), GatePolicy())
    assert c["verdict"] == "pass" and c["ci_pct"] is not None


@pytest.mark.parametrize(("n", "k", "accepted"), [(19, 3, False), (34, 2, False), (34, 3, True)])
def test_repair_decision_path_requires_complete_evidence(n, k, accepted):
    # Exercise comparison, acceptance and summary generation together; no endpoint or GPU.
    result = repair_perf_check(
        {
            "base": sruns(n=n, k=k, spread=0.01),
            "pr_head": sruns(scale=2, n=n, k=k, spread=0.01),
            "candidate": sruns(n=n, k=k, spread=0.01),
        },
        GatePolicy(),
    )
    assert result["within_budget"] is accepted
    assert result["summary"] and result["reasons"]
