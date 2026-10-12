"""Perf-gate revision: development analysis on existing unchanged-code (A/A) data only.

  uv run python bench/gate_dev_analysis.py

Inputs: raw per-request TTFTs from the two valid A/A studies (2026-10-11 3 runs per side,
2026-10-12 5 runs per side). No repair (RQ5) or regression data is read here: the statistic
and interval were chosen on unchanged-code noise alone, before the revised gate was
validated on fresh runs (docs/gate-revision.md).

Excluded, with reasons: gate_noise_x4 (AC power lost mid-run, labeled invalid in
2026-10-11-gate-ci/NOTES.md); the 2026-10-09 A/A studies (summaries only, no per-request
samples; the 'no warmup' one measured a method since replaced).

Output: bench/results/2026-10-12-gate-revision/dev_analysis.{json,md}
"""

from __future__ import annotations

import itertools
import statistics
from typing import Any

import numpy as np
from common import RESULTS, md_table, read_json, results_dir, write_json
from furnace.guardian.tdist import t_quantile

SOURCES = [
    ("2026-10-11-gate-ci/gate_noise.json", 3),
    ("2026-10-12-gate-ci/gate_noise_r5.json", 5),
]
TOL, CONF = 0.10, 0.90  # tolerance (plan warn_pct) and two-sided confidence (5% per tail)


def load() -> list[dict[str, Any]]:
    out = []
    for f, k in SOURCES:
        for i, t in enumerate(read_json(RESULTS / f)["trials"]):
            out.append({"src": f, "trial": i + 1, "k": k, **t["samples_ms"]})
    return out


def run_stat(run: list[float], name: str) -> float:
    a = np.asarray(run, float)
    if name == "gmean":
        return float(np.log(a).mean())
    if name == "mean":
        return float(np.log(a.mean()))
    if name.startswith("p"):
        return float(np.log(np.percentile(a, float(name[1:]))))
    if name == "trim":
        s = np.sort(a)
        k = max(1, int(len(a) * 0.1))
        return float(np.log(s[k:-k].mean()))
    raise ValueError(name)


def welch(a: list[float], b: list[float], conf: float = CONF) -> tuple[float, float, float]:
    """(difference of means, lower, upper) of b - a with a Welch t interval."""
    x, y = np.asarray(a), np.asarray(b)
    va, vb = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = float(np.sqrt(va + vb))
    d = float(y.mean() - x.mean())
    if se == 0:
        return d, d, d
    df = (va + vb) ** 2 / (va**2 / (len(x) - 1) + vb**2 / (len(y) - 1))
    q = t_quantile(1 - (1 - conf) / 2, df)
    return d, d - q * se, d + q * se


def verdict(lo: float, hi: float, tol: float = TOL) -> str:
    if np.expm1(hi) <= tol:
        return "pass"
    return "fail" if np.expm1(lo) > tol else "inconclusive"


def subsets(t: dict[str, Any], k: int) -> list[tuple[int, ...]]:
    n = len(t["baseline"])
    return list(itertools.combinations(range(n), k)) if n >= k else []


def main() -> None:
    data = load()
    runs = [r for t in data for side in ("baseline", "value") for r in t[side]]
    res: dict[str, Any] = {
        "trials": len(data),
        "runs": len(runs),
        "requests_per_run": sorted({len(r) for r in runs}),
    }

    # --- B. dependence inside a run -------------------------------------------------
    near = [float(np.mean(np.abs(np.diff(r)) / np.asarray(r[:-1]) < 0.03)) for r in runs]
    ac = []
    for r in runs:
        x = np.log(r) - np.log(r).mean()
        ac.append(float((x[:-1] * x[1:]).sum() / (x * x).sum()))
    res["within_run"] = {
        "consecutive_requests_within_3pct": statistics.mean(near),
        "lag1_autocorrelation_log_ttft": statistics.mean(ac),
    }
    # variance components for the run-level geometric mean (log scale)
    per_trial = [[run_stat(r, "gmean") for r in t["baseline"] + t["value"]] for t in data]
    within = float(
        np.sqrt(
            sum(((np.asarray(v) - np.mean(v)) ** 2).sum() for v in per_trial)
            / (sum(len(v) for v in per_trial) - len(per_trial))
        )
    )
    between_trial = float(np.std([np.mean(v) for v in per_trial], ddof=1))
    # consecutive-run correlation (measurement order is not stored; use side order a0,b0,a1...)
    seq_pairs = []
    for t in data:
        seq = [x for pair in zip(t["baseline"], t["value"], strict=False) for x in pair]
        v = np.array([run_stat(r, "gmean") for r in seq])
        v = v - v.mean()
        if len(v) > 2:
            seq_pairs.append(float((v[:-1] * v[1:]).sum() / (v * v).sum()))
    res["gmean_variance"] = {
        "sd_between_trial_means": between_trial,
        "sd_runs_within_trial": within,
        "icc_trial": between_trial**2 / (between_trial**2 + within**2),
        "mean_lag1_corr_consecutive_runs": statistics.mean(seq_pairs),
        "sd_run_log_p95": float(np.std([run_stat(r, "p95") for r in runs], ddof=1)),
        "sd_run_log_gmean": float(np.std([run_stat(r, "gmean") for r in runs], ddof=1)),
    }
    pd_, ind = [], []
    for t in data:
        a = np.array([run_stat(r, "gmean") for r in t["baseline"]])
        b = np.array([run_stat(r, "gmean") for r in t["value"]])
        pd_ += list(b - a)
        ind += list(a - a.mean()) + list(b - b.mean())
    res["pairing"] = {
        "sd_paired_differences": float(np.std(pd_, ddof=1)),
        "sd_expected_if_unpaired": float(np.sqrt(2) * np.std(ind, ddof=1)),
    }

    # --- C. statistic x aggregation: spread of the A/A log ratio -----------------------
    cmp_rows = []
    for stat in ("p95", "p90", "p75", "p50", "mean", "gmean", "trim"):
        for agg in ("median of runs", "pooled requests"):
            lr = []
            for t in data:

                def side(rs: list[list[float]], agg=agg, stat=stat) -> float:
                    if agg == "pooled requests":
                        return float(np.exp(run_stat(list(np.concatenate(rs)), stat)))
                    return float(np.median([np.exp(run_stat(r, stat)) for r in rs]))

                lr.append(float(np.log(side(t["value"]) / side(t["baseline"]))))
            a = np.asarray(lr)
            cmp_rows.append(
                {
                    "statistic": stat,
                    "aggregate": agg,
                    "sd_log_ratio": float(a.std(ddof=1)),
                    "max_abs_change_pct": float(100 * np.expm1(np.abs(a).max())),
                }
            )
    res["statistics"] = cmp_rows

    # --- D. interval for the CURRENT statistic: stored bootstrap vs run-level t --------
    boot_w, t_w = [], []
    for f, _k in SOURCES:
        for t in read_json(RESULTS / f)["trials"]:
            lo, hi = t["ci_pct"]
            boot_w.append(hi - lo)
    for t in data:
        a = [run_stat(r, "p95") for r in t["baseline"]]
        b = [run_stat(r, "p95") for r in t["value"]]
        _, lo, hi = welch(a, b, 0.95)
        t_w.append(100 * (np.expm1(hi) - np.expm1(lo)))
    res["p95_interval_widths_95pct"] = {
        "stored_bootstrap_median_pts": statistics.median(boot_w),
        "run_level_t_median_pts": statistics.median(t_w),
    }

    # --- E. frozen rule on the development data (descriptive; selected on these data) ---
    ops = []
    for stat in ("gmean", "p95"):
        for k in (3, 4, 5):
            v, w = [], []
            for t in data:
                for c in subsets(t, k):
                    a = [run_stat(t["baseline"][i], stat) for i in c]
                    b = [run_stat(t["value"][i], stat) for i in c]
                    _d, lo, hi = welch(a, b)
                    v.append(verdict(lo, hi))
                    w.append(100 * (np.expm1(hi) - np.expm1(lo)))
            ops.append(
                {
                    "statistic": stat,
                    "runs_per_side": k,
                    "subsets": len(v),
                    "pass": v.count("pass") / len(v),
                    "inconclusive": v.count("inconclusive") / len(v),
                    "fail": v.count("fail") / len(v),
                    "median_width_pts": statistics.median(w),
                }
            )
    res["development_operating_characteristics"] = ops
    res["settings"] = {"tolerance_pct": 100 * TOL, "confidence_two_sided": CONF}

    out = results_dir()
    write_json(out / "dev_analysis.json", res)
    lines = [
        "# Perf-gate revision: development analysis (unchanged-code data only)",
        "",
        f"{res['trials']} A/A trials, {res['runs']} runs, {res['requests_per_run']} measured requests "
        "per run, c=8, lab vLLM, 780 MHz. Raw data: `2026-10-11-gate-ci/gate_noise.json` (3 runs "
        "per side), `2026-10-12-gate-ci/gate_noise_r5.json` (5 runs per side). Excluded: "
        "`gate_noise_x4` (AC lost mid-run), 2026-10-09 studies (no per-request samples).",
        "",
        "## Dependence",
        "",
        f"- Within a run, {res['within_run']['consecutive_requests_within_3pct']:.0%} of consecutive "
        "requests have TTFT within 3% of the previous one (closed-loop waves share a scheduler "
        f"step); lag-1 autocorrelation of log TTFT {res['within_run']['lag1_autocorrelation_log_ttft']:.2f}. "
        "Requests in a run are not independent; a 34-request run holds roughly 4-5 waves.",
        f"- Run-level geometric mean (log scale): SD across runs {res['gmean_variance']['sd_runs_within_trial']:.3f} "
        f"within a trial, SD of trial means {res['gmean_variance']['sd_between_trial_means']:.3f} "
        f"(ICC {res['gmean_variance']['icc_trial']:.2f}); correlation of consecutive runs "
        f"{res['gmean_variance']['mean_lag1_corr_consecutive_runs']:.2f}. Run-level SD of log p95 is "
        f"{res['gmean_variance']['sd_run_log_p95']:.3f} vs {res['gmean_variance']['sd_run_log_gmean']:.3f} for the geometric mean.",
        f"- Pairing runs by repeat does not help: SD of paired differences {res['pairing']['sd_paired_differences']:.3f} "
        f"vs {res['pairing']['sd_expected_if_unpaired']:.3f} if unpaired.",
        "",
        "## Statistic and aggregation (SD of the A/A log ratio, lower is better)",
        "",
        md_table(
            ["statistic", "aggregate over runs", "SD of log ratio", "largest |change| (%)"],
            [
                [
                    r["statistic"],
                    r["aggregate"],
                    f"{r['sd_log_ratio']:.3f}",
                    f"{r['max_abs_change_pct']:.1f}",
                ]
                for r in cmp_rows
            ],
            "llrr",
        ),
        "",
        "Pooling requests across runs is the worst for tail percentiles (a single slow run sets the "
        "pooled p95); it only helps location statistics slightly.",
        "",
        "## Interval for the current statistic (p95), 95% intervals",
        "",
        f"Stored hierarchical-bootstrap interval, median width {res['p95_interval_widths_95pct']['stored_bootstrap_median_pts']:.1f} points; "
        f"run-level Welch t interval on the same runs, median width {res['p95_interval_widths_95pct']['run_level_t_median_pts']:.1f} points. "
        "The bootstrap over 3 or 5 runs is about 15% narrower than the run-level t interval: a modest "
        "difference, but in the optimistic direction, because few runs give few distinct resamples.",
        "",
        "## Frozen rule on the development data (descriptive: selected on these data)",
        "",
        f"Tolerance {100 * TOL:.0f}%, two-sided {CONF:.0%} t interval on run-level values "
        "(5% per tail). Every k-run subset of each trial's runs; subsets from one trial are correlated.",
        "",
        md_table(
            [
                "statistic",
                "runs/side",
                "subsets",
                "PASS",
                "INCONCLUSIVE",
                "FAIL (false)",
                "median interval width (pts)",
            ],
            [
                [
                    o["statistic"],
                    o["runs_per_side"],
                    o["subsets"],
                    f"{o['pass']:.0%}",
                    f"{o['inconclusive']:.0%}",
                    f"{o['fail']:.0%}",
                    f"{o['median_width_pts']:.1f}",
                ]
                for o in ops
            ],
            "lrrrrrr",
        ),
    ]
    (out / "dev_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
