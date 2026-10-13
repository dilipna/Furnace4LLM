"""Quality-constrained serving-config selection (the Inference Lab optimizer).

  maximize goodput  s.t.  quality is not worse than the baseline config by more than
                          `quality_tol_pts` (paired interval, question as the unit),
                          failure rate <= max_failure_rate, p95 TTFT <= slo_ttft_p95_ms

This module only decides; `bench/optimize.py` measures. Rules, chosen before any grid was
measured (docs/optimizer.md):

- Quality: per question, the share of sampled answers that pass a deterministic check
  (several seeds per question). Questions are the unit: a config's quality difference to
  the baseline is the mean of per-question differences with a two-sided `confidence` t
  interval (paired: both configs answer the same questions). A config meets the constraint
  only if the interval's lower bound is at or above -quality_tol_pts for every metric;
  "not shown" is not "worse", but it is not feasible either.
- Performance: each config is measured in several runs; goodput, p95 TTFT and failure rate
  are medians across runs, and the min-max range is kept.
- Choice: the feasible config with the highest median goodput. Feasible configs whose
  goodput range overlaps the winner's are reported as indistinguishable; if the baseline is
  among them, the recommendation is to keep it (no change is justified by the data).
- Cost: self-hosted on one GPU with no $/GPU-hour configured, so cost is "N/A" and the
  ranking is by goodput alone, as the plan specifies.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from furnace.guardian.tdist import t_quantile


@dataclass
class OptimizerPolicy:
    quality_tol_pts: float = 5.0  # percentage points
    confidence: float = 0.90  # two-sided; the lower bound is a 95% one-sided limit
    max_failure_rate: float = 0.01
    slo_ttft_p95_ms: float = 500.0


@dataclass
class ConfigResult:
    name: str
    params: dict[str, Any]
    goodput_rps: list[float] = field(default_factory=list)  # one value per performance run
    ttft_p95_ms: list[float] = field(default_factory=list)
    failure_rate: list[float] = field(default_factory=list)
    # metric -> question -> share of sampled answers that passed (0..1)
    quality: dict[str, dict[str, float]] = field(default_factory=dict)
    launch_error: str | None = None


def paired_diff_ci(
    base: dict[str, float], other: dict[str, float], confidence: float
) -> tuple[float, float, float, int]:
    """(mean difference, low, high, n) in percentage points of `other - base`, over the
    questions both answered, with a t interval on the per-question differences."""
    keys = sorted(set(base) & set(other))
    d = [100.0 * (other[k] - base[k]) for k in keys]
    n = len(d)
    if n == 0:
        raise ValueError("no common questions")
    m = statistics.fmean(d)
    if n == 1:
        return m, float("-inf"), float("inf"), n
    sd = statistics.stdev(d)
    if sd == 0:
        return m, m, m, n
    half = t_quantile(1 - (1 - confidence) / 2, n - 1) * sd / n**0.5
    return m, m - half, m + half, n


def _range(xs: list[float]) -> tuple[float, float] | None:
    return (min(xs), max(xs)) if xs else None


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """a is at least as good as b on goodput, every quality mean and p95 TTFT, and better on one."""
    ge = [
        a["goodput_rps"] >= b["goodput_rps"],
        a["ttft_p95_ms"] <= b["ttft_p95_ms"],
        *(a["quality_pct"][m] >= b["quality_pct"][m] for m in a["quality_pct"]),
    ]
    gt = [
        a["goodput_rps"] > b["goodput_rps"],
        a["ttft_p95_ms"] < b["ttft_p95_ms"],
        *(a["quality_pct"][m] > b["quality_pct"][m] for m in a["quality_pct"]),
    ]
    return all(ge) and any(gt)


def select(
    results: list[ConfigResult], baseline: str, policy: OptimizerPolicy | None = None
) -> dict[str, Any]:
    policy = policy or OptimizerPolicy()
    by = {r.name: r for r in results}
    if baseline not in by or by[baseline].launch_error:
        raise ValueError(f"baseline {baseline!r} was not measured")
    base = by[baseline]
    rows: list[dict[str, Any]] = []
    for r in results:
        row: dict[str, Any] = {"name": r.name, "params": r.params, "baseline": r.name == baseline}
        if r.launch_error:
            rows.append(
                {**row, "feasible": False, "reasons": [f"did not launch: {r.launch_error[:200]}"]}
            )
            continue
        row |= {
            "goodput_rps": statistics.median(r.goodput_rps),
            "goodput_range": _range(r.goodput_rps),
            "ttft_p95_ms": statistics.median(r.ttft_p95_ms),
            "ttft_p95_range": _range(r.ttft_p95_ms),
            "failure_rate": statistics.median(r.failure_rate),
            "runs": len(r.goodput_rps),
            "quality_pct": {m: 100 * statistics.fmean(q.values()) for m, q in r.quality.items()},
            "quality_vs_baseline": {},
        }
        reasons = []
        if row["failure_rate"] > policy.max_failure_rate:
            reasons.append(
                f"failure rate {row['failure_rate']:.1%} > {policy.max_failure_rate:.0%}"
            )
        if row["ttft_p95_ms"] > policy.slo_ttft_p95_ms:
            reasons.append(
                f"p95 TTFT {row['ttft_p95_ms']:.0f} ms > SLO {policy.slo_ttft_p95_ms:.0f} ms"
            )
        for m, q in r.quality.items():
            if m not in base.quality:
                reasons.append(f"quality metric {m} has no baseline")
                continue
            diff, lo, hi, n = paired_diff_ci(base.quality[m], q, policy.confidence)
            row["quality_vs_baseline"][m] = {"diff_pts": diff, "ci_pts": [lo, hi], "questions": n}
            if r.name != baseline and lo < -policy.quality_tol_pts:
                worse = hi < -policy.quality_tol_pts
                reasons.append(
                    f"{m}: {diff:+.1f} pts vs baseline (interval {lo:+.1f} to {hi:+.1f}); "
                    + ("worse than" if worse else "not shown within")
                    + f" the {policy.quality_tol_pts:g}-point tolerance"
                )
        rows.append({**row, "feasible": not reasons, "reasons": reasons})

    measured = [r for r in rows if "goodput_rps" in r]
    for r in measured:
        r["pareto"] = not any(_dominates(o, r) for o in measured if o is not r)
    feasible = [r for r in measured if r["feasible"]]
    if not feasible:
        return {
            "rows": rows,
            "pick": None,
            "ties": [],
            "recommendation": "no config meets the constraints",
        }
    top = max(feasible, key=lambda r: r["goodput_rps"])
    lo_top = top["goodput_range"][0]
    ties = [r["name"] for r in feasible if r is not top and r["goodput_range"][1] >= lo_top]
    if top["baseline"]:
        rec = f"keep {top['name']}: no feasible config has higher median goodput"
    elif baseline in ties:
        rec = (
            f"keep {baseline}: {top['name']} has the highest median goodput, but its run range "
            f"overlaps the baseline's, so the data do not justify a change"
        )
    else:
        rec = f"switch to {top['name']}" + (
            f" (indistinguishable from {', '.join(ties)} on goodput)" if ties else ""
        )
    return {"rows": rows, "pick": top["name"], "ties": ties, "recommendation": rec}


# ------------------------------------------------------------------ independent confirmation


def confirmation_target(sel: dict[str, Any], baseline: str) -> tuple[str | None, str]:
    """Which config the confirmation rerun compares with the baseline, and why. The pick when
    it is not the baseline; when the baseline is the pick, the feasible config with the next
    highest median goodput (the closest challenger), so 'keep the baseline' is tested too."""
    if sel.get("pick") is None:
        return None, "no config met the constraints: nothing to confirm"
    if sel["pick"] != baseline:
        return sel["pick"], "the selected config (highest median goodput among feasible configs)"
    others = [
        r for r in sel["rows"] if r.get("feasible") and not r["baseline"] and "goodput_rps" in r
    ]
    if not others:
        return None, "the baseline is the only feasible config: nothing to compare"
    best = max(others, key=lambda r: r["goodput_rps"])
    return best["name"], "the baseline was selected; this is the closest feasible challenger"


def welch_ratio_ci(
    base: list[float], other: list[float], confidence: float
) -> tuple[float, float, float]:
    """(change, low, high) in percent of other/base, from a Welch t interval on the logs (run
    as the unit). Values must be positive."""
    if min(base + other) <= 0:
        raise ValueError("values must be positive for a ratio interval")
    import math

    x = [math.log(v) for v in base]
    y = [math.log(v) for v in other]
    va = statistics.variance(x) / len(x)
    vb = statistics.variance(y) / len(y)
    d = statistics.fmean(y) - statistics.fmean(x)
    se = (va + vb) ** 0.5
    if se == 0:
        lo = hi = d
    else:
        df = (va + vb) ** 2 / (va**2 / (len(x) - 1) + vb**2 / (len(y) - 1))
        q = t_quantile(1 - (1 - confidence) / 2, df)
        lo, hi = d - q * se, d + q * se
    return (math.expm1(d) * 100, math.expm1(lo) * 100, math.expm1(hi) * 100)


def confirm(
    base: ConfigResult, cand: ConfigResult, policy: OptimizerPolicy | None = None
) -> dict[str, Any]:
    """Decide the independent rerun (fresh launches, alternating order, new seeds; rules in
    docs/optimizer.md, fixed before the grid was measured). Outcomes:
      confirmed      goodput higher with the interval above 0, quality within tolerance
                     (same paired rule as selection), failures and p95 SLO met;
      not confirmed: no improvement   the goodput interval's upper bound is at or below 0;
      not confirmed: constraints      goodput higher, but quality/failures/SLO not shown;
      inconclusive   the goodput interval contains 0."""
    policy = policy or OptimizerPolicy()
    if len(base.goodput_rps) < 2 or len(cand.goodput_rps) < 2:
        return {"outcome": "inconclusive", "reasons": ["fewer than 2 runs per side"]}
    out: dict[str, Any] = {}
    reasons: list[str] = []
    if min(base.goodput_rps + cand.goodput_rps) <= 0:
        return {
            "outcome": "inconclusive",
            "reasons": ["a run had zero SLO goodput: no ratio interval"],
            "goodput_rps": {"base": base.goodput_rps, "candidate": cand.goodput_rps},
        }
    g, glo, ghi = welch_ratio_ci(base.goodput_rps, cand.goodput_rps, policy.confidence)
    p, plo, phi = welch_ratio_ci(base.ttft_p95_ms, cand.ttft_p95_ms, policy.confidence)
    out["goodput_change_pct"] = {"change": g, "ci": [glo, ghi]}
    out["ttft_p95_change_pct"] = {"change": p, "ci": [plo, phi]}
    out["quality_vs_baseline"] = {}
    for m, q in cand.quality.items():
        diff, lo, hi, n = paired_diff_ci(base.quality.get(m, {}), q, policy.confidence)
        out["quality_vs_baseline"][m] = {"diff_pts": diff, "ci_pts": [lo, hi], "questions": n}
        if lo < -policy.quality_tol_pts:
            reasons.append(
                f"{m}: {diff:+.1f} pts (interval {lo:+.1f} to {hi:+.1f}) not shown within "
                f"the {policy.quality_tol_pts:g}-point tolerance"
            )
    fr = statistics.median(cand.failure_rate) if cand.failure_rate else 0.0
    if fr > policy.max_failure_rate:
        reasons.append(f"failure rate {fr:.1%} > {policy.max_failure_rate:.0%}")
    p95 = statistics.median(cand.ttft_p95_ms)
    if p95 > policy.slo_ttft_p95_ms:
        reasons.append(f"p95 TTFT {p95:.0f} ms > SLO {policy.slo_ttft_p95_ms:.0f} ms")
    if ghi <= 0:
        outcome = "not confirmed: no improvement"
    elif glo > 0:
        outcome = "confirmed" if not reasons else "not confirmed: constraints"
    else:
        outcome = "inconclusive"
    return {"outcome": outcome, "reasons": reasons, **out}
