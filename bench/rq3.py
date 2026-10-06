"""FurnaceBench RQ3: impact-aware selection vs running the full suite.

For every F1 PR scenario (fixtures/scenarios/f1_scenarios.py) the FULL F1 suite is
executed against base and head on the lab endpoint; its FAIL verdicts are the regression
ground truth. The targeted run is the subset Guard's impact analysis selects. Because the
targeted items are the same executions, their verdicts are identical by construction;
the cost of the targeted run is the measured wall time of the selected items plus the
impact-analysis time. (A separately executed targeted run would add measurement noise on
the perf gate but no new information about selection.)

Ground-truth limits, reported per scenario: the suite runs every revision against the
same live endpoint, so serving-config changes (R5 prefix caching off, model swap) are not
deployed and cannot fail anything; the judge item is SKIP without a key.

  uv run poe bench-rq3 [--scenarios a,b]
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from common import (
    f1_questions,
    fmt,
    manifest,
    md_table,
    read_json,
    require_ac_power,
    results_dir,
    write_json,
)
from f1_scenarios import SCENARIOS, materialize
from f1_suite import F1_SUITE
from furnace.guardian.execute import GuardContext, prepare, run_items, selected_items, verdict
from furnace.guardian.impact import analyze_impact, analyze_tree
from furnace.guardian.report import check_run
from furnace_bench.schema import AdapterName, BenchTarget

TARGET = BenchTarget(
    adapter=AdapterName.vllm, base_url="http://localhost:8100/v1", model="lab", label="lab vLLM"
)
ENDPOINT_ITEMS = {"check:citation_required", "check:context_budget", "bench:chat_perf_gate"}
SEEDED = {  # what the scenario author intended; compared with what the full suite observed
    "r1_dynamic_head": "R1 prefix instability",
    "r2_context_bloat": "R2 context bloat",
    "r3_citation_strip": "R3 citations dropped",
    "r3b_chunk_regex_strip": "R3b ineffective tag strip",
    "r4_approval_removed": "R4 approval gate removed",
    "r5_prefix_caching_off": "R5 prefix caching off (serving config)",
}


def run_scenario(s, questions: list[str], out: Path) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="rq3-"))
    try:
        base_root = materialize(None, tmp / "base")
        head_root = materialize(s, tmp / "head")
        t0 = time.monotonic()
        impact = analyze_impact(analyze_tree(base_root), analyze_tree(head_root), F1_SUITE)
        impact_s = time.monotonic() - t0
        work, base, head = prepare(base_root, head_root)
        ctx = GuardContext(
            base=base, head=head, questions=questions, target=TARGET, max_prompt_tokens=4096 - 256
        )
        print(f"== {s.name}: running the full suite ({len(F1_SUITE)} items)", flush=True)
        full = run_items(F1_SUITE, ctx, progress=lambda m: print("   ", m, flush=True))
        shutil.rmtree(work, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sel = {i.key for i in selected_items(impact, F1_SUITE)}
    by_key = {r.key: r for r in full}
    fails = sorted(k for k, r in by_key.items() if r.verdict == "fail")
    warns = sorted(k for k, r in by_key.items() if r.verdict == "warn")
    targeted = [by_key[i.key] for i in F1_SUITE if i.key in sel]
    cr = check_run(impact, targeted, verdict(targeted))
    (out / f"{s.name}.targeted.check.md").write_text(
        f"# {cr['title']}\n\nconclusion: {cr['conclusion']}\n\n{cr['summary']}\n\n{cr['text']}\n",
        encoding="utf-8",
    )
    rec = {
        "scenario": s.name,
        "description": s.description,
        "seeded": SEEDED.get(s.name),
        "categories": sorted(impact.categories),
        "fell_back_to_full": impact.impact.fell_back_to_full,
        "impact_seconds": impact_s,
        "selected": sorted(sel),
        "skipped": [{"key": x.key, "reason": x.reason} for x in impact.impact.skipped],
        "full": [
            {"key": r.key, "verdict": r.verdict, "seconds": r.seconds, "detail": r.detail}
            for r in full
        ],
        "full_fail": fails,
        "full_warn": warns,
        "missed_fail": [k for k in fails if k not in sel],
        "missed_warn": [k for k in warns if k not in sel],
        "full_seconds": sum(r.seconds for r in full),
        "targeted_seconds": sum(by_key[k].seconds for k in sel) + impact_s,
        "full_endpoint_seconds": sum(r.seconds for r in full if r.key in ENDPOINT_ITEMS),
        "targeted_endpoint_seconds": sum(by_key[k].seconds for k in sel if k in ENDPOINT_ITEMS),
        "judge_tokens_est": {
            "full": sum(i.cost.get("llm_tokens", 0) for i in F1_SUITE),
            "targeted": sum(i.cost.get("llm_tokens", 0) for i in F1_SUITE if i.key in sel),
        },
        "targeted_conclusion": cr["conclusion"],
        "full_conclusion": verdict(full),
    }
    write_json(out / f"{s.name}.json", rec)
    return rec


def summarize(recs: list[dict[str, Any]]) -> dict[str, Any]:
    n_full = len(F1_SUITE)
    fails = sum(len(r["full_fail"]) for r in recs)
    caught = fails - sum(len(r["missed_fail"]) for r in recs)
    warns = sum(len(r["full_warn"]) for r in recs)
    caught_w = warns - sum(len(r["missed_warn"]) for r in recs)
    return {
        "scenarios": len(recs),
        "suite_items": n_full,
        "items_executed_pct": sum(len(r["selected"]) for r in recs) / (n_full * len(recs)) * 100,
        "wall_seconds": {
            "full": sum(r["full_seconds"] for r in recs),
            "targeted": sum(r["targeted_seconds"] for r in recs),
        },
        "endpoint_seconds": {
            "full": sum(r["full_endpoint_seconds"] for r in recs),
            "targeted": sum(r["targeted_endpoint_seconds"] for r in recs),
        },
        "judge_tokens_est": {
            "full": sum(r["judge_tokens_est"]["full"] for r in recs),
            "targeted": sum(r["judge_tokens_est"]["targeted"] for r in recs),
        },
        "regression_recall": {
            "caught": caught,
            "total": fails,
            "recall": caught / fails if fails else None,
        },
        "warn_recall": {"caught": caught_w, "total": warns},
        "conclusion_agreement": sum(r["targeted_conclusion"] == r["full_conclusion"] for r in recs),
    }


def render(res: dict[str, Any]) -> str:
    s = res["summary"]
    rr = s["regression_recall"]
    lines = [
        "# RQ3: impact-aware selection vs the full suite",
        "",
        f"{s['scenarios']} PR scenarios on F1, {s['suite_items']}-item suite, lab vLLM (Qwen2.5-0.5B) on the laptop GPU. "
        "Ground truth = FAIL verdicts of the full suite on that scenario.",
        "",
        md_table(
            ["metric", "full suite", "targeted"],
            [
                ["suite items executed", "100%", f"{s['items_executed_pct']:.0f}%"],
                [
                    "wall time (s, all scenarios)",
                    fmt(s["wall_seconds"]["full"], 0),
                    fmt(s["wall_seconds"]["targeted"], 0),
                ],
                [
                    "endpoint-busy time (s)",
                    fmt(s["endpoint_seconds"]["full"], 0),
                    fmt(s["endpoint_seconds"]["targeted"], 0),
                ],
                [
                    "judge tokens (cost-model estimate; judge not run)",
                    f"{s['judge_tokens_est']['full']:,}",
                    f"{s['judge_tokens_est']['targeted']:,}",
                ],
                [
                    "regressions caught (FAIL)",
                    f"{rr['total']}",
                    f"{rr['caught']} (recall {fmt(rr['recall'], 2)})",
                ],
                [
                    "warnings caught (WARN)",
                    f"{s['warn_recall']['total']}",
                    f"{s['warn_recall']['caught']}",
                ],
                [
                    "check conclusion equals full-suite conclusion",
                    "–",
                    f"{s['conclusion_agreement']}/{s['scenarios']}",
                ],
            ],
            "lrr",
        ),
        "",
        "## Per scenario",
        "",
        md_table(
            [
                "scenario",
                "selected",
                "full-suite FAIL",
                "full-suite WARN",
                "missed by targeting",
                "wall s full → targeted",
            ],
            [
                [
                    r["scenario"],
                    f"{len(r['selected'])}/{s['suite_items']}"
                    + (" (fallback)" if r["fell_back_to_full"] else ""),
                    ", ".join(r["full_fail"]) or "–",
                    ", ".join(r["full_warn"]) or "–",
                    ", ".join(r["missed_fail"] + [f"{w} (warn)" for w in r["missed_warn"]])
                    or "none",
                    f"{r['full_seconds']:.0f} → {r['targeted_seconds']:.0f}",
                ]
                for r in res["scenarios"]
            ],
            "llllll",
        ),
        "",
        "## Seeded regressions the full suite did not catch (suite sensitivity, not selection)",
        "",
    ]
    for r in res["scenarios"]:
        if r["seeded"] and not r["full_fail"]:
            why = (
                "serving config is not deployed per revision; every revision runs on the same endpoint"
                if "serving" in (r["seeded"] or "")
                else "see per-item details in the scenario JSON"
            )
            lines.append(
                f"- **{r['scenario']}** ({r['seeded']}): no FAIL in the full suite; WARN: {', '.join(r['full_warn']) or 'none'}. {why}."
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scenarios", help="comma-separated subset")
    p.add_argument("--allow-battery", action="store_true", help="run on battery (labeled)")
    p.add_argument("--rerun", action="store_true", help="ignore stored scenario results")
    args = p.parse_args()
    out = results_dir("rq3")
    questions = f1_questions()
    names = args.scenarios.split(",") if args.scenarios else [s.name for s in SCENARIOS]
    recs = []
    for s in SCENARIOS:
        if s.name not in names:
            continue
        stored = out / f"{s.name}.json"
        if stored.exists() and not args.rerun:
            recs.append(read_json(stored))
            continue
        require_ac_power(args.allow_battery)  # checked per scenario: power can change mid-run
        recs.append(run_scenario(s, questions, out))
    res = {"manifest": manifest(), "summary": summarize(recs), "scenarios": recs}
    write_json(out.parent / "rq3.json", res)
    (out.parent / "rq3.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
