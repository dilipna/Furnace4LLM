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
Trials marked as affected by competing work (gate_validate.py mark-affected) are left out of
the primary tally and shown again in a row that includes them. The p95 (tail) comparison is
reported in its own table: it is advisory and never decides a verdict.

Output: <same dir>/report.{json,md}
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from common import RESULTS, md_table, write_json
from furnace.guardian.perf_gate import GatePolicy, compare
from gate_validate import affected_trials, clopper_pearson

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


def tail_summary(trials: list[dict[str, Any]], tol: float = 10.0) -> dict[str, Any]:
    """The advisory p95 comparison: how often its own 90% interval rules a tail regression
    beyond the tolerance out (upper <= tol), establishes one (lower > tol), or neither."""
    p = [t["p95_advisory"] for t in trials if t.get("p95_advisory")]
    if not p:
        return {"n": 0}
    ch = [x["change_pct"] for x in p]
    return {
        "n": len(p),
        "ruled_out": sum(x["ci_pct"][1] <= tol for x in p),
        "established": sum(x["ci_pct"][0] > tol for x in p),
        "unresolved": sum(not (x["ci_pct"][1] <= tol or x["ci_pct"][0] > tol) for x in p),
        "change_median": float(np.median(ch)),
        "change_range": [min(ch), max(ch)],
        "width_median": float(np.median([x["ci_pct"][1] - x["ci_pct"][0] for x in p])),
    }


def summarize_set(name: str, j: dict[str, Any], include_affected: bool = False) -> dict[str, Any]:
    skip = set() if include_affected else affected_trials(j)
    kept = [t for t in j["trials"] if t["trial"] not in skip]
    trials = [t for t in kept if t.get("verdict") != "error"]
    errors = [t for t in kept if t.get("verdict") == "error"]
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
        "affected": sorted(affected_trials(j)),
        "affected_included": include_affected,
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
        "tail_p95": tail_summary(trials),
        "ci_width_median": float(np.median([t["ci_pct"][1] - t["ci_pct"][0] for t in trials]))
        if n
        else None,
    }
    return out


RATIONALE = """\
## Why this metric, interval and these thresholds

All three were fixed in `docs/gate-revision.md` before any trial here ran, and none is changed
after seeing these results.

- **Geometric-mean TTFT per run.** A run has 34 requests, and requests in a run are not
  independent (closed-loop waves at c=8 share scheduler steps). A run's p95 is its 2nd-3rd
  largest value, set by one or two waves; the geometric mean uses every request. On the
  development A/A data its run-to-run SD (log scale) was 0.056 against 0.112 for p95, so it
  resolves about half the change for the same cost. It compares as a ratio, which matches
  how the regressions Furnace targets act (lost prefix cache, longer context and a bigger model
  scale the whole TTFT distribution) and how a different GPU clock acts.
- **The run as the unit, 90% two-sided Welch interval.** Each run is reduced to one number, so
  the dependence between requests stays inside it and the run-to-run spread already contains
  it. Resampling requests (the replaced bootstrap) treated dependent requests as independent
  and gave intervals about 15% too narrow. Welch is used because base and candidate runs of
  the same repeat were measured to be no more alike than runs of different repeats. A
  two-sided 90% interval is a one-sided 95% statement in each direction: PASS means "a
  regression above 10% is ruled out at 95%", FAIL means "a regression above 10% is
  established at 95%".
- **10% tolerance, 25% block.** These are the plan's policy values, set before any
  measurement as the size of latency change worth stopping a merge for, and kept as they were
  rather than fitted to the noise. On this machine unchanged code moves the geometric mean by
  up to about 13-15% between trials, which is why the decision uses the interval and not the
  point change. A true change near 10% is expected to come out INCONCLUSIVE: that is the
  gate's resolution at 3 runs per side, not something to tune away.

## What this gate does not do

It is a latency-location gate, not a tail-SLO gate. A change confined to the slowest few
percent of requests, with the typical request unchanged, is not detected unless it also
moves the geometric mean. The p95 table above is reported for that reason. It is advisory:
with 3 runs per side its interval is too wide to confirm a 10% tolerance. Not covered: other
GPUs, clocks, models or workloads, concurrency other than 8, and GitHub-hosted runners.
"""


def main() -> None:
    sets, sets_all = {}, {}
    for p in sorted(DIR.glob("v*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        sets[j["set"]] = summarize_set(j["set"], j)
        if affected_trials(j):
            sets_all[j["set"]] = summarize_set(j["set"], j, include_affected=True)
    names = [s for s in ORDER if s in sets] + [s for s in sets if s not in ORDER]

    def row(label: str, s: str, r: dict[str, Any]) -> list[Any]:
        n = r["trials"]
        fails = r["warn"] + r["block"]
        lo, hi = r["fail_rate_ci95"] or (0, 1)
        o = r["old_rule"]
        return [
            label,
            CALIBRATED_SIZE.get(s, "none (unchanged)"),
            f"{n}/{r['requested']}",
            r["pass"],
            r["inconclusive"],
            r["warn"],
            r["block"],
            f"{fails}/{n} ({lo:.0%}-{hi:.0%})",
            f"{r['change_median']:+.1f}% ({r['change_range'][0]:+.1f} to {r['change_range'][1]:+.1f})",
            f"{r['ci_width_median']:.1f}",
            f"{r['interval_contains_0'][0]}/{r['interval_contains_0'][1]}"
            if s in NULL_SETS
            else "–",
            f"{o['pass']}/{o['inconclusive']}/{o['warn']}/{o['block']}",
        ]

    rows = []
    for s in names:
        rows.append(row(s, s, sets[s]))
        if s in sets_all:
            rows.append(row(f"{s}, incl. affected trials {sets[s]['affected']}", s, sets_all[s]))

    def null_line(src: dict[str, dict[str, Any]], label: str) -> str:
        null = [src.get(s) or sets[s] for s in NULL_SETS if s in sets]
        nn = sum(r["trials"] for r in null)
        nf = sum(r["warn"] + r["block"] for r in null)
        npass = sum(r["pass"] for r in null)
        lo, hi = clopper_pearson(nf, nn) if nn else (0, 1)
        return (
            f"{label}: false FAIL {nf}/{nn} (exact 95% CI {lo:.1%} to {hi:.1%}), PASS {npass}/{nn}."
        )

    targets = []
    for s in NULL_SETS:
        if s in sets:
            r = sets[s]
            fr = (r["warn"] + r["block"]) / r["trials"]
            pr = r["pass"] / r["trials"]
            partial = (
                ""
                if r["trials"] >= r["requested"]
                else f" [partial: {r['trials']}/{r['requested']}]"
            )
            targets.append(
                f"- {s}: false FAIL {fr:.0%} (target <= 10%: {'met' if fr <= 0.10 else 'NOT met'}), "
                f"PASS {pr:.0%} (target >= 70%: {'met' if pr >= 0.70 else 'NOT met'}){partial}"
            )
    if "v3a_r1" in sets:
        r = sets["v3a_r1"]
        targets.append(
            f"- v3a_r1: BLOCK in {r['block']}/{r['trials']} (target: all: "
            f"{'met' if r['block'] == r['trials'] else 'NOT met'})"
        )
    tail_rows = []
    for s in names:
        t = sets[s]["tail_p95"]
        if t["n"]:
            tail_rows.append(
                [
                    s,
                    t["n"],
                    f"{t['change_median']:+.1f}% ({t['change_range'][0]:+.1f} to {t['change_range'][1]:+.1f})",
                    f"{t['width_median']:.1f}",
                    t["ruled_out"],
                    t["established"],
                    t["unresolved"],
                ]
            )
    mism = {s: sets[s]["recompute_mismatches"] for s in names if sets[s]["recompute_mismatches"]}
    clocks = [c for s in names if sets[s]["sm_clock_mhz"] for c in sets[s]["sm_clock_mhz"]]
    text = [
        "# Perf-gate validation: fresh trials under the frozen rule",
        "",
        "Every trial is the real gate path (prompts rendered from each revision in the sandbox, 3 "
        "interleaved runs per side, c=8, 34 requests per run). Rule frozen in `docs/gate-revision.md` "
        "(6e90c99; implemented 26fa8eb; sizes for the graded sets fixed in 9d80db8 before any trial). "
        "The last column applies the rule that was replaced to the same raw samples. Trials "
        "affected by competing work on the machine are left out of the primary row, replaced, and "
        "shown again in an 'incl. affected' row (rule: `../NOTES.md`)."
        + (
            f" SM clock across all trials: {min(clocks):.0f}-{max(clocks):.0f} MHz."
            if clocks
            else ""
        ),
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
                "interval width, median (pts)",
                "interval contains 0",
                "old rule on same data: P/I/W/B",
            ],
            rows,
        ),
        "",
        null_line({}, "Unchanged code (V1 + V2 together)"),
        *([null_line(sets_all, "The same, including affected trials")] if sets_all else []),
        "",
        "Pre-declared targets (primary rows):",
        *targets,
        "",
        "## Tail latency (p95), reported separately; advisory, never decides a verdict",
        "",
        "Same trials and runs: each run's p95 TTFT, compared with the same run-level 90% Welch "
        "interval. 'Ruled out' = interval upper bound <= 10%; 'established' = lower bound > 10%.",
        "",
        md_table(
            [
                "set",
                "trials",
                "p95 change, median (range)",
                "interval width, median (pts)",
                "tail regression > 10% ruled out",
                "established",
                "unresolved",
            ],
            tail_rows,
        ),
        "",
        RATIONALE,
        "Bookkeeping: verdicts recomputed from the stored raw samples (rounded to 0.01 ms) "
        + (
            "equal the recorded ones in every trial; interval bounds agree within "
            f"{max(sets[s]['recompute_max_ci_diff_pts'] for s in names):.1f} point (rounding)."
            if not mism
            else f"DIFFER in {mism}."
        ),
    ]
    write_json(DIR / "report.json", {"sets": sets, "sets_including_affected": sets_all})
    (DIR / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
