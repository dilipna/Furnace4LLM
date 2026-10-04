"""Judge calibration against trusted human labels.

Convention: the *positive* class is FAIL (the judge's job is to detect a failure
mode). TPR = share of human-FAIL items the judge flags; TNR = share of human-PASS
items the judge passes.

A judge's raw failure rate on unlabeled data is biased by its errors. With known
TPR/TNR, the Rogan-Gladen estimator corrects it:
    theta = (p_obs + TNR - 1) / (TPR + TNR - 1)
which is only defined when TPR + TNR > 1 (better than chance).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from furnace.contracts.evals import Calibration, Verdict

TRUST_TPR = 0.8
TRUST_TNR = 0.8


@dataclass(frozen=True)
class LabeledPair:
    human: Verdict  # PASS | FAIL
    judge: Verdict  # PASS | FAIL (ERROR/SKIP pairs are excluded before calibration)


def _ratio(a: int, b: int) -> float | None:
    return a / b if b else None


def calibrate(
    pairs: Sequence[LabeledPair], *, label_set_version: str, split: str = "test"
) -> Calibration:
    usable = [
        p
        for p in pairs
        if p.human in (Verdict.PASS, Verdict.FAIL) and p.judge in (Verdict.PASS, Verdict.FAIL)
    ]
    tp = sum(p.human == Verdict.FAIL and p.judge == Verdict.FAIL for p in usable)
    fn = sum(p.human == Verdict.FAIL and p.judge == Verdict.PASS for p in usable)
    tn = sum(p.human == Verdict.PASS and p.judge == Verdict.PASS for p in usable)
    fp = sum(p.human == Verdict.PASS and p.judge == Verdict.FAIL for p in usable)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall
        else (0.0 if precision == 0 or recall == 0 else None)
    )
    return Calibration(
        n=len(usable),
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        tpr=recall,
        tnr=_ratio(tn, tn + fp),
        label_set_version=label_set_version,
        split=split,
    )


def is_trusted(
    c: Calibration, *, min_tpr: float = TRUST_TPR, min_tnr: float = TRUST_TNR, min_n: int = 20
) -> bool:
    return (
        c.n >= min_n
        and c.tpr is not None
        and c.tnr is not None
        and c.tpr >= min_tpr
        and c.tnr >= min_tnr
    )


def rogan_gladen(p_obs: float, tpr: float, tnr: float) -> float | None:
    """Bias-corrected true failure rate, clipped to [0, 1]; None if the judge is not better than chance."""
    denom = tpr + tnr - 1.0
    if denom <= 0:
        return None
    return min(1.0, max(0.0, (p_obs + tnr - 1.0) / denom))


def corrected_failure_rate(
    judge_verdicts: Sequence[Verdict],
    calibration_pairs: Sequence[LabeledPair],
    *,
    n_boot: int = 2000,
    seed: int = 0,
) -> tuple[float | None, tuple[float, float] | None]:
    """Point estimate and 95% bootstrap CI, resampling both the unlabeled verdicts and
    the labeled calibration set (so judge uncertainty widens the interval)."""
    verdicts = [v for v in judge_verdicts if v in (Verdict.PASS, Verdict.FAIL)]
    if not verdicts or not calibration_pairs:
        return None, None

    def estimate(vs: Sequence[Verdict], ps: Sequence[LabeledPair]) -> float | None:
        c = calibrate(ps, label_set_version="boot")
        if c.tpr is None or c.tnr is None:
            return None
        return rogan_gladen(sum(v == Verdict.FAIL for v in vs) / len(vs), c.tpr, c.tnr)

    point = estimate(verdicts, calibration_pairs)
    rng = random.Random(seed)  # noqa: S311 - statistical resampling, not security
    samples: list[float] = []
    for _ in range(n_boot):
        vs = [verdicts[rng.randrange(len(verdicts))] for _ in verdicts]
        ps = [calibration_pairs[rng.randrange(len(calibration_pairs))] for _ in calibration_pairs]
        est = estimate(vs, ps)
        if est is not None:
            samples.append(est)
    if len(samples) < n_boot * 0.5:
        return point, None
    samples.sort()
    lo = samples[int(0.025 * (len(samples) - 1))]
    hi = samples[int(0.975 * (len(samples) - 1))]
    return point, (lo, hi)


def split_items(
    ids: Sequence[str], *, seed: int = 0, train: float = 0.2, dev: float = 0.4
) -> dict[str, str]:
    """Deterministic train/dev/test assignment. Few-shot examples come only from train;
    the judge is tuned on dev and reported on test."""
    order = sorted(ids)
    random.Random(seed).shuffle(order)  # noqa: S311 - reproducible data split
    n = len(order)
    n_train, n_dev = round(n * train), round(n * dev)
    return {
        i: ("train" if k < n_train else "dev" if k < n_train + n_dev else "test")
        for k, i in enumerate(order)
    }
