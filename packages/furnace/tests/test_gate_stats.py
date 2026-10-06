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
