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


def test_block_requires_separated_runs():
    pol = GatePolicy()
    c = compare(runs(600, 620, 610), runs(1500, 1480, 1520), pol)
    assert c["verdict"] == "block" and c["separated"]
    noisy = compare(runs(300, 600, 450), runs(420, 900, 500), pol)  # +11% median, overlapping
    assert noisy["verdict"] == "warn" and not noisy["separated"]
    big_overlap = compare(
        runs(300, 900, 400), runs(800, 350, 700), pol
    )  # +75% median but overlapping
    assert big_overlap["verdict"] == "warn"
    assert compare(runs(500, 510), runs(505, 495), pol)["verdict"] == "pass"


def test_single_run_can_still_block():
    assert compare(runs(500), runs(700), GatePolicy())["verdict"] == "block"


def test_conclusion_mapping():
    r = lambda v: ItemResult("k", v, "")  # noqa: E731
    assert verdict([r("pass"), r("skip")]) == "success"
    assert verdict([r("pass"), r("warn")]) == "neutral"
    assert verdict([r("error")]) == "neutral"
    assert verdict([r("warn"), r("fail")]) == "failure"


# ------------------------------------------------- interval-based decisions (real gate path)

import numpy as np  # noqa: E402
from furnace.guardian.perf_gate import (  # noqa: E402
    METHOD_BOOTSTRAP,
    METHOD_POINT,
    accept_repair,
    run_order,
)


class _S:
    """A run with per-request TTFT samples, like perf_gate.VariantResult."""

    def __init__(self, xs):
        self.xs = list(xs)

    def samples(self, name):
        return self.xs

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
    assert c["method"] == METHOD_BOOTSTRAP and c["verdict"] == "pass"
    lo, hi = c["ci_pct"]
    assert lo <= 0 <= hi and hi <= 10
    assert len(c["samples_ms"]["baseline"]) == 3 and len(c["samples_ms"]["value"][0]) == 200


def test_large_separated_regression_blocks():
    c = compare(sruns(seed=1), sruns(scale=10, seed=2), GatePolicy())
    assert c["verdict"] == "block" and c["ci_pct"][0] > 10 and c["separated"]


def test_confident_but_small_regression_warns():
    c = compare(
        sruns(seed=1, n=300, spread=0.02), sruns(1.18, seed=2, n=300, spread=0.02), GatePolicy()
    )
    assert c["verdict"] == "warn" and c["ci_pct"][0] > 10 and c["change_pct"] < 25


def test_noise_that_straddles_the_tolerance_is_inconclusive_not_pass():
    c = compare(sruns(seed=1, spread=0.3), sruns(1.08, seed=2, spread=0.3), GatePolicy())
    lo, hi = c["ci_pct"]
    assert lo <= 10 < hi and c["verdict"] == "inconclusive"


def test_summaries_without_samples_use_the_labeled_point_rule():
    c = compare(runs(600, 620, 610), runs(1500, 1480, 1520), GatePolicy())
    assert c["method"] == METHOD_POINT and c["ci_pct"] is None


def test_interval_is_reproducible_for_a_fixed_seed():
    a, b = sruns(seed=3), sruns(1.05, seed=4)
    assert compare(a, b, GatePolicy())["ci_pct"] == compare(a, b, GatePolicy())["ci_pct"]


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
