"""Perf-gate noise calibration (A/A): the gate comparing F1's main branch with itself.

  uv run python bench/gate_noise.py [--trials 12]

Each trial runs the real gate path (prompts rendered from each revision inside the sandbox,
3 interleaved repeats, concurrency 8) on two identical copies of F1 main, so every change it
reports is run-to-run noise. Output: bench/results/<date>/gate_noise.{json,md} with each
trial's change, the verdict the current policy would give, and whether the runs separated.
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from common import f1_questions, manifest, md_table, power_state, results_dir, write_json
from f1_scenarios import materialize
from furnace.guardian.execute import prepare
from furnace.guardian.perf_gate import GatePolicy, compare, run_gate
from furnace_bench.schema import AdapterName, BenchTarget

TARGET = BenchTarget(
    adapter=AdapterName.vllm, base_url="http://localhost:8100/v1", model="lab", label="lab vLLM"
)


def trial(
    questions: list[str], policy: GatePolicy, mult: int = 1, repeats: int = 3
) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="gate-aa-"))
    try:
        a = materialize(None, tmp / "a")
        b = materialize(None, tmp / "b")
        work, base, same = prepare(a, b)
        try:
            t0 = time.monotonic()
            res = run_gate(
                {"a": base, "b": same},
                questions,
                TARGET,
                concurrency=8,
                request_multiplier=mult,
                repeats=repeats,
            )
            secs = time.monotonic() - t0
        finally:
            shutil.rmtree(work, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    c = compare(res["a"], res["b"], policy)
    clocks = [
        lv.telemetry.get("gpu_sm_clock_mhz_mean")
        for vs in res.values()
        for v in vs
        for lv in v.report.levels
        if lv.telemetry.get("gpu_sm_clock_mhz_mean") is not None
    ]
    return {**c, "seconds": round(secs, 1), "sm_clock_mhz": clocks}


def render(res: dict[str, Any]) -> str:
    rows = res["trials"]
    if not rows:
        return f"# Perf-gate noise calibration (A/A)\n\nNo valid trial: {res.get('stopped')}\n"
    ch = [r["change_pct"] for r in rows]
    abs_sorted = sorted(abs(x) for x in ch)
    lines = [
        "# Perf-gate noise calibration (A/A)",
        "",
        f"F1 main vs an identical copy of F1 main, {len(rows)} gate runs, each {res.get('repeats', 3)} interleaved "
        f"repeats per side at concurrency 8 (the real gate path), "
        f"{res.get('requests_per_run', 34)} measured requests per run. Any change below is noise.",
        "",
        md_table(
            [
                "trial",
                "geo-mean TTFT a (ms)",
                "geo-mean TTFT b (ms)",
                "change",
                "interval",
                "runs separated",
                "verdict (policy)",
                "SM MHz",
            ],
            [
                [
                    i + 1,
                    r["baseline"],
                    r["value"],
                    f"{r['change_pct']:+.1f}%",
                    _ci(r),
                    "yes" if r["separated"] else "no",
                    r["verdict"],
                    f"{min(r['sm_clock_mhz']):.0f}-{max(r['sm_clock_mhz']):.0f}"
                    if r["sm_clock_mhz"]
                    else "–",
                ]
                for i, r in enumerate(rows)
            ],
        ),
        "",
        f"Change: median {statistics.median(ch):+.1f}%, min {min(ch):+.1f}%, max {max(ch):+.1f}%; "
        f"|change| median {statistics.median(abs_sorted):.1f}%, max {abs_sorted[-1]:.1f}%.",
        f"Policy at the time: tolerance {res['policy']['warn_pct']}%, block > "
        f"{res['policy']['block_pct']}% and runs separated. Decision method: "
        f"{rows[0].get('method') or 'point estimate (before 2026-10-11)'}.",
        f"Verdicts: pass {_n(rows, 'pass')}, inconclusive {_n(rows, 'inconclusive')} "
        "(noise too large to decide), "
        f"false WARN {_n(rows, 'warn')}, false BLOCK {_n(rows, 'block')}; "
        f"separated by chance: {sum(r['separated'] for r in rows)}/{len(rows)}.",
    ]
    if res.get("stopped"):
        lines.append(f"Run {res['stopped']}.")
    cis = [r["ci_pct"] for r in rows if r.get("ci_pct")]
    if cis:
        covers = sum(lo <= 0 <= hi for lo, hi in cis)
        widths = sorted(hi - lo for lo, hi in cis)
        lines.append(
            f"Interval check: the {round(res['policy']['confidence'] * 100)}% interval contains 0 (the true A/A difference) in "
            f"{covers}/{len(cis)} trials; width median {statistics.median(widths):.1f} "
            f"percentage points, max {widths[-1]:.1f}."
        )
    return "\n".join(lines) + "\n"


def _ci(r: dict[str, Any]) -> str:
    ci = r.get("ci_pct")
    return f"{ci[0]:+.1f}% to {ci[1]:+.1f}%" if ci else "–"


def _n(rows: list[dict[str, Any]], verdict: str) -> str:
    return f"{sum(r['verdict'] == verdict for r in rows)}/{len(rows)}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=12)
    p.add_argument("--request-multiplier", type=int, default=1, help="questions per run x N")
    p.add_argument("--out-name", default="gate_noise", help="output file stem")
    p.add_argument("--repeats", type=int, default=3, help="interleaved runs per side")
    a = p.parse_args()
    power = power_state()
    if power.get("on_ac") is False:
        raise SystemExit("on battery: GPU numbers would not be comparable; plug in")
    policy = GatePolicy()
    questions = f1_questions()
    rows = []
    stopped = None
    for i in range(a.trials):
        r = trial(questions, policy, a.request_multiplier, a.repeats)
        # Power is checked after every trial, not only at start: on 2026-10-11 the laptop
        # lost AC partway through a run (gate_noise_x4, kept and labeled invalid).
        after = power_state()
        r["power_after"] = after
        if after.get("on_ac") is False:
            stopped = (
                f"stopped after trial {i + 1}: AC power lost during it; that trial is discarded"
            )
            print(stopped, flush=True)
            break
        rows.append(r)
        print(
            f"trial {i + 1}/{a.trials}: {r['baseline']} -> {r['value']} ms "
            f"({r['change_pct']:+.1f}%, {r['verdict']}, separated={r['separated']}) {r['seconds']} s",
            flush=True,
        )
    out = results_dir()
    res = {
        "manifest": manifest(),
        "policy": {
            "warn_pct": policy.warn_pct,
            "block_pct": policy.block_pct,
            "metric": policy.metric,
            "confidence": policy.confidence,
            "min_runs": policy.min_runs,
        },
        "request_multiplier": a.request_multiplier,
        "repeats": a.repeats,
        "requests_per_run": len(questions) * a.request_multiplier,
        "trials": rows,
        "stopped": stopped,
    }
    write_json(out / f"{a.out_name}.json", res)
    (out / f"{a.out_name}.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
