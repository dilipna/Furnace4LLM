"""Fresh validation of the revised perf gate (protocol frozen in docs/gate-revision.md).

  uv run python bench/gate_validate.py run  --set v1_aa [--trials 24]
  uv run python bench/gate_validate.py calibrate-topk --ks 4,6,8,12
  uv run python bench/gate_validate.py summarize

Every trial is the real gate path: both revisions are copied, a harness is generated from
each revision's own code, prompts are rendered inside the sandbox, and furnace-bench replays
them against the lab vLLM (3 interleaved runs per side, concurrency 8, 34 requests per run).
Sets (trial counts from the protocol):
  v1_aa           24 trials  F1 main vs an identical copy (unchanged code)
  v2_restored     12 trials  main vs R1 applied, then the exact inverse edit plus a comment
  v3a_r1           6 trials  main vs R1 (request id prepended to the system prompt)
  v3b_r2           6 trials  main vs R2 (retrieval depth 12, context budget x4)
  v3c_topk<K>      6 trials  main vs retrieval depth K (budget x4), K chosen by calibrate-topk

Rules (declared before running): after every trial AC power is checked; a trial during which
it was lost is discarded, counted and the run stops. A trial that raises is kept as an
'error' and counted; three consecutive errors stop the run. No other trial is dropped, and
no outlier is trimmed. `--smoke` writes under validation_smoke/ and is never counted.

Output: bench/results/<date>/validation/<set>.jsonl (one line per trial, written as it
finishes), <set>.json (manifest + trials), and `summarize` writes validation.md.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from common import (
    f1_questions,
    manifest,
    md_table,
    power_state,
    results_dir,
    write_json,
)
from f1_scenarios import Scenario, by_name, materialize
from furnace.guardian.execute import prepare
from furnace.guardian.perf_gate import GatePolicy, benchmark_variant, compare, run_gate
from furnace_bench.schema import AdapterName, BenchTarget

TARGET = BenchTarget(
    adapter=AdapterName.vllm, base_url="http://localhost:8100/v1", model="lab", label="lab vLLM"
)
DEFAULT_TRIALS = {"v1_aa": 24, "v2_restored": 12, "v3a_r1": 6, "v3b_r2": 6}
GRADED_TRIALS = 6
COMMENT = "\n# restored: the request id was removed again\n"


def topk_scenario(k: int) -> Scenario:
    return Scenario(
        f"topk_{k}",
        f"retrieval depth {k}, context budget x4",
        [
            (
                "config/rag.yaml",
                "top_k: 3\n  max_context_chars: 6000",
                f"top_k: {k}\n  max_context_chars: 24000",
            )
        ],
        {"retrieval_config"},
    )


def restored_tree(dest: Path) -> Path:
    """R1 applied, then undone with the exact inverse edits, plus a comment-only change."""
    sc = by_name("r1_dynamic_head")
    materialize(sc, dest)
    for path, old, new in reversed(sc.edits):
        p = dest / path
        text = p.read_text(encoding="utf-8")
        assert new in text, f"inverse edit target missing in {path}"
        p.write_text(text.replace(new, old, 1), encoding="utf-8")
    prompts = dest / "app" / "prompts.py"
    prompts.write_text(prompts.read_text(encoding="utf-8") + COMMENT, encoding="utf-8")
    return dest


def other_factory(name: str) -> Callable[[Path], Path]:
    if name == "v1_aa":
        return lambda d: materialize(None, d)
    if name == "v2_restored":
        return restored_tree
    if name == "v3a_r1":
        return lambda d: materialize(by_name("r1_dynamic_head"), d)
    if name == "v3b_r2":
        return lambda d: materialize(by_name("r2_context_bloat"), d)
    if name.startswith("v3c_topk"):
        k = int(name.removeprefix("v3c_topk"))
        return lambda d: materialize(topk_scenario(k), d)
    raise SystemExit(f"unknown set {name}")


def vllm_image() -> str | None:
    try:
        r = subprocess.run(
            ["docker", "inspect", "furnace-vllm-1", "--format", "{{.Image}} {{.Config.Image}}"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=20,
        )
        return r.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def one_trial(name: str, questions: list[str], policy: GatePolicy) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="gate-val-"))
    try:
        a = materialize(None, tmp / "a")
        b = other_factory(name)(tmp / "b")
        work, base, other = prepare(a, b)
        try:
            t0 = time.monotonic()
            res = run_gate({"a": base, "b": other}, questions, TARGET, concurrency=8, repeats=3)
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


def run(name: str, trials: int, smoke: bool) -> None:
    pw = power_state()
    if pw.get("on_ac") is False:
        raise SystemExit("on battery: plug in AC power (protocol requires AC)")
    out = results_dir("validation_smoke" if smoke else "validation")
    jsonl = out / f"{name}.jsonl"
    policy, questions = GatePolicy(), f1_questions()
    rows: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []
    consecutive_errors = 0
    stopped = None
    for i in range(trials):
        started = time.strftime("%H:%M:%S", time.gmtime())
        r: dict[str, Any]
        try:
            r = one_trial(name, questions, policy)
            consecutive_errors = 0
        except Exception as exc:  # kept and counted, never dropped
            r = {"verdict": "error", "reason": f"{type(exc).__name__}: {exc}"[:300]}
            consecutive_errors += 1
        r["power_after"] = power_state()
        r["trial"], r["started_utc"] = i + 1, started
        if r["power_after"].get("on_ac") is False:
            discarded.append({**r, "discard_reason": "AC power lost during the trial"})
            stopped = f"stopped after trial {i + 1}: AC power lost; that trial is discarded"
            print(stopped, flush=True)
            break
        rows.append(r)
        with jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, default=str) + "\n")
        ci = r.get("ci_pct")
        print(
            f"{name} {i + 1}/{trials}: {r.get('baseline')} -> {r.get('value')} ms "
            f"({r.get('change_pct')}%, interval {ci}, {r['verdict']}) {r.get('seconds')} s",
            flush=True,
        )
        if consecutive_errors >= 3:
            stopped = f"stopped after trial {i + 1}: three consecutive errors"
            print(stopped, flush=True)
            break
    write_json(
        out / f"{name}.json",
        {
            "set": name,
            "smoke": smoke,
            "requested_trials": trials,
            "manifest": manifest(vllm_image=vllm_image()),
            "policy": policy.__dict__,
            "trials": rows,
            "discarded": discarded,
            "stopped": stopped,
        },
    )


# --------------------------------------------------------------------------- calibration


def calibrate_topk(ks: list[int], runs: int) -> None:
    """Raw effect size of retrieval depth on TTFT (interleaved runs; no gate verdict is used
    to choose sizes, only the measured geometric-mean ratio)."""
    import asyncio

    import numpy as np

    pw = power_state()
    if pw.get("on_ac") is False:
        raise SystemExit("on battery: plug in AC power")
    questions = f1_questions()
    tmp = Path(tempfile.mkdtemp(prefix="gate-cal-"))
    trees: dict[str, Path] = {}
    try:
        base_src = materialize(None, tmp / "main")
        work_dirs = []
        for label, make in [("main", lambda d: base_src)] + [
            (f"topk_{k}", lambda d, k=k: materialize(topk_scenario(k), d)) for k in ks
        ]:
            src = make(tmp / label) if label != "main" else base_src
            w, b, _ = prepare(src, src)
            work_dirs.append(w)
            trees[label] = b

        async def go() -> dict[str, list[float]]:
            vals: dict[str, list[float]] = {k: [] for k in trees}
            for r in range(runs):
                names = list(trees)
                rot = names[r % len(names) :] + names[: r % len(names)]
                for n in rot:
                    v = await benchmark_variant(n, trees[n], questions, TARGET, concurrency=8)
                    vals[n].append(float(np.log(v.ttft_ms).mean()))
            return vals

        vals = asyncio.run(go())
        for w in work_dirs:
            shutil.rmtree(w, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    base = float(np.mean(vals["main"]))
    rows = [
        {
            "variant": n,
            "geomean_ms": round(float(np.exp(np.mean(v))), 1),
            "change_pct": round(float(np.expm1(np.mean(v) - base) * 100), 1),
            "runs": len(v),
        }
        for n, v in vals.items()
    ]
    out = results_dir("validation")
    write_json(out / "calibration_topk.json", {"manifest": manifest(), "rows": rows})
    print(
        md_table(
            ["variant", "geometric-mean TTFT (ms)", "change vs main (%)", "runs"],
            [[r["variant"], r["geomean_ms"], r["change_pct"], r["runs"]] for r in rows],
        )
    )


# ------------------------------------------------------------------------------ summary


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided binomial interval."""

    def cdf(x: int, p: float) -> float:
        return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(x + 1))

    def solve(f: Callable[[float], float], target: float) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) > target else (lo, mid)
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, p), alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p), alpha / 2)
    return lower, upper


def summarize() -> None:
    d = results_dir("validation")
    sets = sorted(d.glob("*.json"))
    sets = [s for s in sets if not s.name.startswith("calibration")]
    rows, lines = [], []
    for s in sets:
        j = json.loads(s.read_text(encoding="utf-8"))
        t = j["trials"]
        v = [x["verdict"] for x in t]
        n = len(t)
        fail = v.count("warn") + v.count("block")
        lo, hi = clopper_pearson(fail, n) if n else (0, 1)
        ch = [x["change_pct"] for x in t if x.get("change_pct") is not None]
        rows.append(
            [
                j["set"],
                f"{n}/{j['requested_trials']}",
                v.count("pass"),
                v.count("inconclusive"),
                v.count("warn"),
                v.count("block"),
                v.count("error"),
                f"{fail}/{n} ({lo:.0%}-{hi:.0%})" if n else "–",
                f"{statistics.median(ch):+.1f}%" if ch else "–",
                f"{min(ch):+.1f}% to {max(ch):+.1f}%" if ch else "–",
            ]
        )
        for dd in j.get("discarded", []):
            lines.append(f"- {j['set']} trial {dd['trial']} discarded: {dd['discard_reason']}")
        if j.get("stopped"):
            lines.append(f"- {j['set']}: {j['stopped']}")
        for x in t:
            if x["verdict"] == "error":
                lines.append(f"- {j['set']} trial {x['trial']} error: {x.get('reason')}")
    text = [
        "# Perf-gate validation (fresh runs, protocol in docs/gate-revision.md)",
        "",
        md_table(
            [
                "set",
                "trials done/planned",
                "PASS",
                "INCONCLUSIVE",
                "WARN",
                "BLOCK",
                "error",
                "WARN+BLOCK (exact 95% CI of the rate)",
                "median change",
                "range of change",
            ],
            rows,
        ),
        "",
        "## Exclusions, discards, errors",
        "",
        *(lines or ["None recorded."]),
    ]
    (d / "validation.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--set", required=True)
    r.add_argument("--trials", type=int)
    r.add_argument("--smoke", action="store_true")
    c = sub.add_parser("calibrate-topk")
    c.add_argument("--ks", default="4,6,8,12")
    c.add_argument("--runs", type=int, default=3)
    sub.add_parser("summarize")
    a = p.parse_args()
    if a.cmd == "run":
        n = a.trials or DEFAULT_TRIALS.get(a.set) or GRADED_TRIALS
        run(a.set, n, a.smoke)
    elif a.cmd == "calibrate-topk":
        calibrate_topk([int(x) for x in a.ks.split(",")], a.runs)
    else:
        summarize()


if __name__ == "__main__":
    main()
