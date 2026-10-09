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


def trial(questions: list[str], policy: GatePolicy) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="gate-aa-"))
    try:
        a = materialize(None, tmp / "a")
        b = materialize(None, tmp / "b")
        work, base, same = prepare(a, b)
        try:
            t0 = time.monotonic()
            res = run_gate({"a": base, "b": same}, questions, TARGET, concurrency=8)
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
    ch = [r["change_pct"] for r in rows]
    abs_sorted = sorted(abs(x) for x in ch)
    lines = [
        "# Perf-gate noise calibration (A/A)",
        "",
        f"F1 main vs an identical copy of F1 main, {len(rows)} gate runs, each 3 interleaved "
        "repeats per side at concurrency 8 (the real gate path). Any change below is noise.",
        "",
        md_table(
            [
                "trial",
                "p95 TTFT a (ms)",
                "p95 TTFT b (ms)",
                "change",
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
        f"Policy at the time: warn > {res['policy']['warn_pct']}%, block > {res['policy']['block_pct']}% "
        "and runs separated.",
        f"False WARN: {sum(r['verdict'] == 'warn' for r in rows)}/{len(rows)}; "
        f"false BLOCK: {sum(r['verdict'] == 'block' for r in rows)}/{len(rows)}; "
        f"separated by chance: {sum(r['separated'] for r in rows)}/{len(rows)}.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=12)
    a = p.parse_args()
    power = power_state()
    if power.get("on_ac") is False:
        raise SystemExit("on battery: GPU numbers would not be comparable; plug in")
    policy = GatePolicy()
    questions = f1_questions()
    rows = []
    for i in range(a.trials):
        r = trial(questions, policy)
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
        },
        "trials": rows,
    }
    write_json(out / "gate_noise.json", res)
    (out / "gate_noise.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
