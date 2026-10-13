"""Report for the fresh perf-gate validation (protocol: docs/gate-revision.md sections 5 and 7).

  uv run python bench/gate_validation_report.py

Reads bench/results/2026-10-12-gate-validation/validation/<set>.json (written by
bench/gate_validate.py). For every trial it:
- recomputes the frozen rule from the stored raw per-request TTFTs and checks that it equals
  the verdict the gate recorded at run time (a bookkeeping check, reported);
- applies the rule the revision replaced (median of per-run p95, 95% hierarchical bootstrap,
  "runs separated" for BLOCK; reproduced verbatim from commit 6e90c99) to the SAME samples,
  so the two rules are compared on identical data.
Truth per set: v1_aa and v2_restored have no true change (a FAIL is false; the interval should
contain 0); v3* are real regressions (a FAIL is a detection). Pre-declared targets are
reported as met or not met; nothing here changes a threshold.

Output: <same dir>/report.{json,md}
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from common import RESULTS, md_table, write_json
from furnace.guardian.perf_gate import GatePolicy, compare
from gate_validate import clopper_pearson

DIR = RESULTS / "2026-10-12-gate-validation" / "validation"
NULL_SETS = ("v1_aa", "v2_restored")
ORDER = ["v1_aa", "v2_restored", "v3c_topk4", "v3c_topk8", "v3b_r2", "v3a_r1"]
CALIBRATED_SIZE = {  # raw effect measured before the runs (docs/gate-revision.md section 7)
    "v3c_topk4": "+12.9%",
    "v3c_topk8": "+18.2%",
    "v3b_r2": "about +30% (depth 12)",
    "v3a_r1": "about +800% (earlier studies)",
}


class _Run:
    def __init__(self, xs: list[float]) -> None:
        self.xs = xs

    def samples(self, name: str) -> list[float]:
        return self.xs if name == "ttft_ms" else []

    def metric(self, name: str) -> float | None:
        return float(np.percentile(self.xs, 95)) if name == "ttft_p95_ms" else None


# ---- the replaced rule, verbatim from 6e90c99 (guardian/perf_gate.py) --------------------
def _old_bootstrap_change_ci(base_runs, other_runs, q, *, n_boot=2000, seed=0, confidence=0.95):
    rng = np.random.default_rng(seed)

    def replicates(runs):
        k = len(runs)
        per_run = np.stack(
            [
                np.percentile(a[rng.integers(0, a.size, size=(n_boot, a.size))], q, axis=1)
                for a in runs
            ]
        )
        which = rng.integers(0, k, size=(n_boot, k))
        col = rng.integers(0, n_boot, size=(n_boot, k))
        return np.median(per_run[which, col], axis=1)

    b, o = replicates(base_runs), replicates(other_runs)
    change = (o - b) / b * 100
    tail = (1 - confidence) / 2 * 100
    return float(np.percentile(change, tail)), float(np.percentile(change, 100 - tail))


def old_rule(base: list[list[float]], other: list[list[float]]) -> dict[str, Any]:
    bs = [float(np.percentile(r, 95)) for r in base]
    os_ = [float(np.percentile(r, 95)) for r in other]
    b, o = float(np.median(bs)), float(np.median(os_))
    change = (o - b) / b * 100
    separated = min(os_) > max(bs)
    lo, hi = _old_bootstrap_change_ci(
        [np.asarray(r, float) for r in base], [np.asarray(r, float) for r in other], 95.0
    )
    if hi <= 10.0:
        v = "pass"
    elif lo > 10.0:
        v = "block" if change > 25.0 and (separated or len(bs) == 1) else "warn"
    else:
        v = "inconclusive"
    return {"verdict": v, "change_pct": round(change, 1), "ci_pct": [round(lo, 1), round(hi, 1)]}


# -----------------------------------------------------------------------------------------


def is_fail(v: str) -> bool:
    return v in ("warn", "block")


def summarize_set(name: str, j: dict[str, Any]) -> dict[str, Any]:
    trials = [t for t in j["trials"] if t.get("verdict") != "error"]
    errors = [t for t in j["trials"] if t.get("verdict") == "error"]
    pol = GatePolicy()
    mismatches, old, ci_diff = [], [], 0.0
    for t in trials:
        s = t["samples_ms"]
        rec = compare([_Run(r) for r in s["baseline"]], [_Run(r) for r in s["value"]], pol)
        # Stored samples are rounded to 0.01 ms, so a recomputed bound can differ by one
        # rounding step (0.1 point) from the one the gate computed at full precision.
        d = max(abs(a - b) for a, b in zip(rec["ci_pct"], t["ci_pct"], strict=True))
        ci_diff = max(ci_diff, d)
        if rec["verdict"] != t["verdict"] or d > 0.1 + 1e-9:
            mismatches.append(t["trial"])
        old.append(old_rule(s["baseline"], s["value"]))
    v = [t["verdict"] for t in trials]
    n = len(trials)
    fails = sum(is_fail(x) for x in v)
    cover = [t["ci_pct"][0] <= 0 <= t["ci_pct"][1] for t in trials if t.get("ci_pct")]
    clocks = [c for t in trials for c in t.get("sm_clock_mhz", [])]
    out = {
        "set": name,
        "trials": n,
        "requested": j["requested_trials"],
        "errors": len(errors),
        "discarded": len(j.get("discarded", [])),
        "resumed": j.get("resumed", []),
        "pass": v.count("pass"),
        "inconclusive": v.count("inconclusive"),
        "warn": v.count("warn"),
        "block": v.count("block"),
        "fail_rate_ci95": clopper_pearson(fails, n) if n else None,
        "interval_contains_0": (sum(cover), len(cover)),
        "change_median": float(np.median([t["change_pct"] for t in trials])) if n else None,
        "change_range": [min(t["change_pct"] for t in trials), max(t["change_pct"] for t in trials)]
        if n
        else None,
        "old_rule": {
            k: sum(o["verdict"] == k for o in old)
            for k in ("pass", "inconclusive", "warn", "block")
        },
        "recompute_mismatches": mismatches,
        "recompute_max_ci_diff_pts": round(ci_diff, 2),
        "sm_clock_mhz": [min(clocks), max(clocks)] if clocks else None,
    }
    return out


def main() -> None:
    sets = {}
    for p in sorted(DIR.glob("v*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        sets[j["set"]] = summarize_set(j["set"], j)
    names = [s for s in ORDER if s in sets] + [s for s in sets if s not in ORDER]
    rows = []
    for s in names:
        r = sets[s]
        n = r["trials"]
        fails = r["warn"] + r["block"]
        lo, hi = r["fail_rate_ci95"] or (0, 1)
        o = r["old_rule"]
        rows.append(
            [
                s,
                CALIBRATED_SIZE.get(s, "none (unchanged)"),
                f"{n}/{r['requested']}",
                r["pass"],
                r["inconclusive"],
                r["warn"],
                r["block"],
                f"{fails}/{n} ({lo:.0%}-{hi:.0%})",
                f"{r['change_median']:+.1f}% ({r['change_range'][0]:+.1f} to {r['change_range'][1]:+.1f})",
                f"{r['interval_contains_0'][0]}/{r['interval_contains_0'][1]}"
                if s in NULL_SETS
                else "–",
                f"{o['pass']}/{o['inconclusive']}/{o['warn']}/{o['block']}",
            ]
        )
    null = [sets[s] for s in NULL_SETS if s in sets]
    nn = sum(r["trials"] for r in null)
    nf = sum(r["warn"] + r["block"] for r in null)
    npass = sum(r["pass"] for r in null)
    lo, hi = clopper_pearson(nf, nn) if nn else (0, 1)
    targets = []
    for s in NULL_SETS:
        if s in sets:
            r = sets[s]
            fr = (r["warn"] + r["block"]) / r["trials"]
            pr = r["pass"] / r["trials"]
            targets.append(
                f"- {s}: false FAIL {fr:.0%} (target <= 10%: {'met' if fr <= 0.10 else 'NOT met'}), "
                f"PASS {pr:.0%} (target >= 70%: {'met' if pr >= 0.70 else 'NOT met'})"
            )
    if "v3a_r1" in sets:
        r = sets["v3a_r1"]
        targets.append(
            f"- v3a_r1: BLOCK in {r['block']}/{r['trials']} (target: all: "
            f"{'met' if r['block'] == r['trials'] else 'NOT met'})"
        )
    mism = {s: sets[s]["recompute_mismatches"] for s in names if sets[s]["recompute_mismatches"]}
    text = [
        "# Perf-gate validation: fresh trials under the frozen rule",
        "",
        "Every trial is the real gate path (prompts rendered from each revision in the sandbox, 3 "
        "interleaved runs per side, c=8, 34 requests per run). Rule frozen in `docs/gate-revision.md` "
        "(6e90c99; implemented 26fa8eb; sizes for the graded sets fixed in 9d80db8 before any trial). "
        "The last column applies the rule that was replaced to the same raw samples.",
        "",
        md_table(
            [
                "set",
                "true change",
                "trials",
                "PASS",
                "INCONCL.",
                "WARN",
                "BLOCK",
                "FAIL = WARN+BLOCK (exact 95% CI)",
                "measured change, median (range)",
                "interval contains 0",
                "old rule on same data: P/I/W/B",
            ],
            rows,
        ),
        "",
        f"Unchanged code (V1 + V2 together): false FAIL {nf}/{nn} (exact 95% CI {lo:.1%} to {hi:.1%}), "
        f"PASS {npass}/{nn}.",
        "",
        "Pre-declared targets:",
        *targets,
        "",
        "Bookkeeping: verdicts recomputed from the stored raw samples (rounded to 0.01 ms) "
        + (
            "equal the recorded ones in every trial; interval bounds agree within "
            f"{max(sets[s]['recompute_max_ci_diff_pts'] for s in names):.1f} point (rounding)."
            if not mism
            else f"DIFFER in {mism}."
        ),
    ]
    write_json(DIR / "report.json", {"sets": sets})
    (DIR / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
