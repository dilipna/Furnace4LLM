import pytest
from furnace.contracts.evals import Verdict
from furnace.evals.calibration import (
    LabeledPair,
    calibrate,
    corrected_failure_rate,
    is_trusted,
    rogan_gladen,
    split_items,
)

P, F = Verdict.PASS, Verdict.FAIL


def pairs(tp, fn, tn, fp):
    return (
        [LabeledPair(F, F)] * tp
        + [LabeledPair(F, P)] * fn
        + [LabeledPair(P, P)] * tn
        + [LabeledPair(P, F)] * fp
    )


def test_confusion_metrics_failure_is_positive_class():
    c = calibrate(pairs(tp=8, fn=2, tn=27, fp=3), label_set_version="v1")
    assert (c.tp, c.fn, c.tn, c.fp, c.n) == (8, 2, 27, 3, 40)
    assert c.tpr == pytest.approx(0.8) and c.recall == pytest.approx(0.8)
    assert c.tnr == pytest.approx(0.9)
    assert c.precision == pytest.approx(8 / 11)
    assert c.f1 == pytest.approx(2 * (8 / 11) * 0.8 / ((8 / 11) + 0.8))
    assert is_trusted(c)


def test_untrusted_when_recall_low_or_sample_small():
    assert not is_trusted(calibrate(pairs(tp=5, fn=5, tn=30, fp=0), label_set_version="v1"))
    assert not is_trusted(
        calibrate(pairs(tp=4, fn=0, tn=4, fp=0), label_set_version="v1")
    )  # n < 20


def test_errors_and_skips_are_excluded():
    c = calibrate(
        [LabeledPair(F, Verdict.ERROR), LabeledPair(P, Verdict.SKIP), LabeledPair(F, F)],
        label_set_version="v1",
    )
    assert c.n == 1 and c.tp == 1


def test_rogan_gladen_recovers_true_rate():
    true_rate, tpr, tnr = 0.2, 0.8, 0.9
    p_obs = true_rate * tpr + (1 - true_rate) * (1 - tnr)  # 0.24
    assert rogan_gladen(p_obs, tpr, tnr) == pytest.approx(true_rate)
    assert rogan_gladen(0.3, 0.5, 0.5) is None  # chance-level judge


def test_corrected_rate_with_ci_brackets_point():
    cal = pairs(tp=16, fn=4, tn=36, fp=4)  # tpr .8, tnr .9
    verdicts = [F] * 24 + [P] * 76  # observed .24 -> corrected .2
    point, ci = corrected_failure_rate(verdicts, cal, n_boot=500)
    assert point == pytest.approx(0.2)
    assert ci is not None and point is not None
    assert ci[0] <= point <= ci[1]


def test_split_is_deterministic_and_complete():
    ids = [f"i{k}" for k in range(50)]
    a, b = split_items(ids, seed=3), split_items(list(reversed(ids)), seed=3)
    assert a == b and set(a) == set(ids)
    assert sum(v == "train" for v in a.values()) == 10 and sum(v == "dev" for v in a.values()) == 20
