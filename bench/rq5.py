"""FurnaceBench RQ5: failing-test-first repair, repeated.

R1 (dynamic request id prepended to F1's system prompt) is repaired `--repeats` times
end to end by `repair_prefix_instability` (rule strategy). Each repeat:
  - reproduction: the generated regression test must fail on head and pass on base
  - validation: regression test + existing tests in the sandbox
  - performance: base / PR head / repair benchmarked interleaved (3 runs each)
  - full-suite audit: the complete F1 suite run with the *repaired* tree as the head,
    to catch regressions the repair itself introduces
R2 (context bloat) is attempted once: there is no repair strategy for it, and the
report shows what the loop does in that case. The LLM-patch strategy is not built.

  uv run poe bench-rq5 [--repeats 3]
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
from f1_scenarios import by_name, materialize
from f1_suite import F1_SUITE
from furnace.guardian.execute import GuardContext, prepare, run_items, verdict
from furnace.guardian.impact import analyze_impact, analyze_tree
from furnace.guardian.perf_gate import GatePolicy, compare, run_gate
from furnace.guardian.repair.loop import repair_prefix_instability
from furnace_bench.schema import AdapterName, BenchTarget

TARGET = BenchTarget(
    adapter=AdapterName.vllm, base_url="http://localhost:8100/v1", model="lab", label="lab vLLM"
)


def attempt(
    scenario: str, rep: int, questions: list[str], out: Path, audit: bool
) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="rq5-"))
    keep = tmp / "repaired"
    policy = GatePolicy()
    stages: list[dict[str, Any]] = []
    t0 = time.monotonic()

    def progress(stage: str, msg: str) -> None:
        stages.append({"t": round(time.monotonic() - t0, 1), "stage": stage, "msg": msg})
        print(f"   [{time.monotonic() - t0:6.1f}s] {stage:16s} {msg}", flush=True)

    def perf_check(base: Path, head: Path, cand: Path) -> dict[str, Any]:
        # the loop deletes its work tree; keep the latest candidate for the audit
        shutil.rmtree(keep, ignore_errors=True)
        shutil.copytree(cand, keep)
        res = run_gate(
            {"base": base, "pr_head": head, "candidate": cand}, questions, TARGET, concurrency=8
        )
        hv, cv = (
            compare(res["base"], res["pr_head"], policy),
            compare(res["base"], res["candidate"], policy),
        )
        return {
            "head_vs_base": hv,
            "candidate_vs_base": cv,
            "within_budget": cv["verdict"] in ("pass", "warn"),
            "summary": f"p95 TTFT base {hv['baseline']} | PR {hv['value']} ({hv['change_pct']:+}%, {hv['verdict']}) | repair {cv['value']} ({cv['change_pct']:+}%, {cv['verdict']})",
            "reports": {k: [v.report.model_dump(mode="json") for v in vs] for k, vs in res.items()},
        }

    try:
        base_root = materialize(None, tmp / "base")
        head_root = materialize(by_name(scenario), tmp / "head")
        impact = analyze_impact(analyze_tree(base_root), analyze_tree(head_root), F1_SUITE)
        o = repair_prefix_instability(
            base_root,
            head_root,
            impact,
            questions=questions[:6],
            change_label=scenario,
            progress=progress,
            perf_check=perf_check,
        )
        repair_s = time.monotonic() - t0
        rec: dict[str, Any] = {
            "scenario": scenario,
            "repeat": rep,
            "status": o.attempt.status.value,
            "repro": o.attempt.repro.model_dump() if o.attempt.repro else None,
            "localization": [c.model_dump(mode="json") for c in o.attempt.localization],
            "candidates": [
                {
                    "strategy": c.strategy,
                    "verdict": c.verdict,
                    "perf_summary": (c.results.get("perf") or {}).get("summary"),
                    **{
                        k: v
                        for k, v in c.results.items()
                        if k in ("regression_test", "existing_tests", "explanation")
                    },
                }
                for c in o.attempt.candidates
            ],
            "perf": {k: v for k, v in o.perf.items() if k != "reports"},
            "logs": o.logs,
            "stages": stages,
            "repair_seconds": repair_s,
            "patch": o.patch,
        }
        if o.perf.get("reports"):
            write_json(out / f"{scenario}_r{rep}.perf_reports.json", o.perf["reports"])
        if audit and keep.exists():
            print("   full-suite audit of the repaired tree", flush=True)
            work, base, head = prepare(base_root, keep)
            ctx = GuardContext(
                base=base,
                head=head,
                questions=questions,
                target=TARGET,
                max_prompt_tokens=4096 - 256,
            )
            res = run_items(F1_SUITE, ctx, progress=lambda m: print("     ", m, flush=True))
            shutil.rmtree(work, ignore_errors=True)
            rec["audit"] = {
                "conclusion": verdict(res),
                "items": [
                    {"key": r.key, "verdict": r.verdict, "detail": r.detail, "seconds": r.seconds}
                    for r in res
                ],
                "new_failures": [r.key for r in res if r.verdict == "fail"],
            }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    write_json(out / f"{scenario}_r{rep}.json", rec)
    return rec


def render(res: dict[str, Any]) -> str:
    r1 = [a for a in res["attempts"] if a["scenario"] == "r1_dynamic_head"]
    lines = [
        "# RQ5: failing-test-first repair",
        "",
        f"R1 repaired {len(r1)} times end to end (rule strategy `prefix_stability.move_dynamic_to_suffix`), "
        "lab vLLM Qwen2.5-0.5B on the laptop GPU, perf gate at concurrency 8 with 3 interleaved runs per revision. "
        "The LLM-patch strategy is not built, so there is no rule-vs-LLM comparison.",
        "",
        md_table(
            [
                "repeat",
                "status",
                "fails on head / passes on base",
                "regression test",
                "existing tests",
                "PR p95 TTFT vs base",
                "repair p95 TTFT vs base",
                "repair hit rate",
                "audit (full suite on repair)",
                "time (s)",
            ],
            [
                [
                    a["repeat"],
                    a["status"],
                    f"{a['repro']['head_fails']} / {a['repro']['base_passes']}"
                    if a["repro"]
                    else "–",
                    (a["candidates"][0].get("regression_test") if a["candidates"] else "–"),
                    (a["candidates"][0].get("existing_tests") if a["candidates"] else "–"),
                    _cmp(a["perf"].get("head_vs_base")),
                    _cmp(a["perf"].get("candidate_vs_base")),
                    _hit(a["perf"].get("candidate_vs_base")),
                    (a.get("audit") or {}).get("conclusion", "–")
                    + (
                        f" (FAIL: {', '.join(a['audit']['new_failures'])})"
                        if (a.get("audit") or {}).get("new_failures")
                        else ""
                    ),
                    fmt(a["repair_seconds"], 0),
                ]
                for a in r1
            ],
            "rlllllllll",
        ),
        "",
        f"Success: {sum(a['status'] == 'verified' for a in r1)}/{len(r1)} verified repairs; "
        f"{sum(not (a.get('audit') or {}).get('new_failures') and 'audit' in a for a in r1)}/{len(r1)} audits without a FAIL.",
    ]
    for a in r1:
        audit = a.get("audit")
        if audit:
            nonpass = [i for i in audit["items"] if i["verdict"] != "pass"]
            if nonpass:
                lines.append(
                    f"\nRepeat {a['repeat']} audit, items not PASS: "
                    + "; ".join(
                        f"`{i['key']}` {i['verdict'].upper()}: {i['detail'][:150]}" for i in nonpass
                    )
                )
    others = [a for a in res["attempts"] if a["scenario"] != "r1_dynamic_head"]
    for a in others:
        lines += [
            "",
            f"## {a['scenario']} (attempt)",
            "",
            f"Status `{a['status']}`. " + "; ".join(f"{k}: {v}" for k, v in a["logs"].items()),
        ]
    return "\n".join(lines) + "\n"


def _cmp(c: dict[str, Any] | None) -> str:
    if not c:
        return "–"
    return f"{c['baseline']} → {c['value']} ms ({c['change_pct']:+.1f}%, {c['verdict']})"


def _hit(c: dict[str, Any] | None) -> str:
    h = (c or {}).get("prefix_hit_rate") or (None, None)
    return "–" if h[1] is None else f"{h[0] * 100:.0f}% → {h[1] * 100:.0f}%"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--allow-battery", action="store_true", help="run on battery (labeled)")
    p.add_argument("--no-audit", action="store_true")
    args = p.parse_args()
    out = results_dir("rq5")
    q = f1_questions()
    attempts = []
    plan = [("r1_dynamic_head", r) for r in range(args.repeats)] + [("r2_context_bloat", 0)]
    for scen, rep in plan:
        stored = out / f"{scen}_r{rep}.json"
        if stored.exists():
            attempts.append(read_json(stored))
            continue
        require_ac_power(args.allow_battery)  # checked per item: power can change mid-run
        print(f"== {scen} repeat {rep}", flush=True)
        attempts.append(
            attempt(scen, rep, q, out, audit=not args.no_audit and scen == "r1_dynamic_head")
        )
    res = {"manifest": manifest(), "attempts": attempts}
    write_json(out.parent / "rq5.json", res)
    (out.parent / "rq5.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
