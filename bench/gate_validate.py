"""Fresh validation of the revised perf gate (protocol frozen in docs/gate-revision.md).

  uv run python bench/gate_validate.py run  --set v1_aa [--trials 24]
  uv run python bench/gate_validate.py mark-affected --set v1_aa --trials 9 --reason "..."
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
'error' and counted; three consecutive errors stop the run. No outlier is trimmed.
`--smoke` writes under validation_smoke/ and is never counted.

Affected trials (rule added 2026-10-13 at the owner's direction, before V1 trial 15; see
bench/results/2026-10-12-gate-validation/NOTES.md): a trial during which competing compute
ran on the machine (a test run, lint/format/type check, build, Docker or sandbox job,
benchmark or analysis script that is not part of the trial), established from a command log
and never from the trial's result, is marked with `mark-affected`. It stays in the record
with its result, is left out of the primary tally, and is replaced: `run` continues until
the set holds the requested number of unaffected trials. Reports also show the tally with
the affected trials included. Each trial records the machine's CPU busy share while it ran
(data only; no rule uses it). A JSONL line cut off by a kill is kept aside, never parsed
into a trial.

Output: bench/results/<date>/validation/<set>.jsonl (one line per trial, written as it
finishes), <set>.json (manifest + trials), and `summarize` writes validation.md.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import shutil
import statistics
import subprocess
import tempfile
import threading
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


def _system_times() -> tuple[int, int] | None:
    """(busy, total) CPU time of the whole machine so far, in 100 ns units (Windows only)."""
    if platform.system() != "Windows":
        return None
    import ctypes
    from ctypes import wintypes

    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(  # type: ignore[attr-defined]
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        return None

    def v(f: Any) -> int:
        return (f.dwHighDateTime << 32) | f.dwLowDateTime

    total = v(kernel) + v(user)  # kernel time includes idle time
    return total - v(idle), total


class CpuSampler:
    """The machine's CPU busy share over a trial (mean) and its largest 1 s value. It includes
    the trial's own work (client, sandbox, the vLLM container), so it is comparable across
    trials, not by itself a measure of competing work."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._max = 0.0
        self._first = _system_times()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self.result: dict[str, Any] | None = None

    def _loop(self) -> None:
        prev = self._first
        while prev is not None and not self._stop.wait(1.0):
            cur = _system_times()
            if cur is None:
                return
            if cur[1] > prev[1]:
                self._max = max(self._max, (cur[0] - prev[0]) / (cur[1] - prev[1]))
            prev = cur

    def __enter__(self) -> CpuSampler:
        self._t.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._t.join(timeout=5)
        last = _system_times()
        if self._first is not None and last is not None and last[1] > self._first[1]:
            mean = (last[0] - self._first[0]) / (last[1] - self._first[1])
            self.result = {
                "busy_mean_pct": round(100 * mean, 1),
                "busy_max_1s_pct": round(100 * self._max, 1),
            }


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


def read_trials(jsonl: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Complete trials from the JSONL, and any line that is not valid JSON (a write cut off
    by a kill), which is returned separately and never counted as a trial."""
    rows: list[dict[str, Any]] = []
    broken: list[str] = []
    if jsonl.exists():
        for x in jsonl.read_text(encoding="utf-8").splitlines():
            if not x.strip():
                continue
            try:
                rows.append(json.loads(x))
            except json.JSONDecodeError:
                broken.append(x)
    return rows, broken


def affected_trials(j: dict[str, Any]) -> set[int]:
    return {int(a["trial"]) for a in j.get("affected", [])}


def run(name: str, trials: int, smoke: bool, resume_note: str | None = None) -> None:
    """Runs set `name` until it holds `trials` unaffected trials. If the set's JSONL already
    holds trials (a run that was killed: the machine slept, Docker stopped), they are kept as
    they are, numbering continues after them, and the restart is recorded in `resumed` with
    `resume_note`. A trial cut off by the kill left no row and is simply run again."""
    pw = power_state()
    if pw.get("on_ac") is False:
        raise SystemExit("on battery: plug in AC power (protocol requires AC)")
    out = results_dir("validation_smoke" if smoke else "validation")
    jsonl = out / f"{name}.jsonl"
    final = out / f"{name}.json"
    policy, questions = GatePolicy(), f1_questions()
    rows, broken = read_trials(jsonl)
    prior = json.loads(final.read_text(encoding="utf-8")) if final.exists() else {}
    discarded: list[dict[str, Any]] = list(prior.get("discarded", []))
    resumed: list[dict[str, Any]] = list(prior.get("resumed", []))
    affected: list[dict[str, Any]] = list(prior.get("affected", []))
    skip = affected_trials(prior)
    if broken:  # keep the cut-off text, rewrite the JSONL with complete trials only
        with (out / f"{name}.jsonl.cut").open("a", encoding="utf-8") as f:
            f.write("\n".join(broken) + "\n")
        jsonl.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), encoding="utf-8")
    if rows:
        if not resume_note:
            raise SystemExit(
                f"{jsonl} already holds {len(rows)} trials: pass --resume-note '<why the run "
                "stopped>' to continue it (the note is recorded), or move the file away"
            )
        resumed.append(
            {
                "after_trial": len(rows),
                "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "note": resume_note,
                **({"cut_lines": len(broken)} if broken else {}),
            }
        )
    consecutive_errors = 0
    stopped = None

    def flush() -> None:
        write_json(
            final,
            {
                "set": name,
                "smoke": smoke,
                "requested_trials": trials,
                "manifest": manifest(vllm_image=vllm_image()),
                "policy": policy.__dict__,
                "trials": rows,
                "affected": affected,
                "discarded": discarded,
                "resumed": resumed,
                "stopped": stopped,
            },
        )

    def counted() -> int:
        return sum(1 for r in rows if r["trial"] not in skip)

    while counted() < trials:
        i = len(rows)
        started = time.strftime("%H:%M:%S", time.gmtime())
        r: dict[str, Any]
        with CpuSampler() as cpu:
            try:
                r = one_trial(name, questions, policy)
                consecutive_errors = 0
            except Exception as exc:  # kept and counted, never dropped
                r = {"verdict": "error", "reason": f"{type(exc).__name__}: {exc}"[:300]}
                consecutive_errors += 1
        r["cpu"] = cpu.result
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
        flush()
        ci = r.get("ci_pct")
        print(
            f"{name} {i + 1} ({counted()}/{trials} counted): {r.get('baseline')} -> "
            f"{r.get('value')} ms ({r.get('change_pct')}%, interval {ci}, {r['verdict']}) "
            f"{r.get('seconds')} s, cpu {r['cpu']}",
            flush=True,
        )
        if consecutive_errors >= 3:
            stopped = f"stopped after trial {i + 1}: three consecutive errors"
            print(stopped, flush=True)
            break
    flush()


def mark_affected(name: str, trial_nos: list[int], reason: str, evidence: str) -> None:
    """Record trials of a set as affected by competing work. Their results stay; they leave
    the primary tally and a later `run` replaces them."""
    final = results_dir("validation") / f"{name}.json"
    j = json.loads(final.read_text(encoding="utf-8"))
    have = {t["trial"] for t in j["trials"]}
    missing = [t for t in trial_nos if t not in have]
    if missing:
        raise SystemExit(f"{name} has no trial {missing}")
    already = affected_trials(j)
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    j.setdefault("affected", []).extend(
        {"trial": t, "reason": reason, "evidence": evidence, "marked_at_utc": at}
        for t in trial_nos
        if t not in already
    )
    write_json(final, j)


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

    def solve(f: Callable[[float], float], target: float, increasing: bool) -> float:
        """The p in (0, 1) with f(p) = target, for f monotone in p."""
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            below = f(mid) < target
            lo, hi = (mid, hi) if below == increasing else (lo, mid)
        return (lo + hi) / 2

    # lower: P(X >= k | p) = alpha/2 (increasing in p); upper: P(X <= k | p) = alpha/2 (decreasing)
    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, p), alpha / 2, increasing=True)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p), alpha / 2, increasing=False)
    return lower, upper


def summarize() -> None:
    d = results_dir("validation")
    sets = sorted(d.glob("v*.json"))  # not calibration_*.json or report.json
    rows, lines = [], []

    def row(label: str, t: list[dict[str, Any]], requested: str) -> list[Any]:
        v = [x["verdict"] for x in t]
        n = len(t)
        fail = v.count("warn") + v.count("block")
        lo, hi = clopper_pearson(fail, n) if n else (0, 1)
        ch = [x["change_pct"] for x in t if x.get("change_pct") is not None]
        return [
            label,
            requested,
            v.count("pass"),
            v.count("inconclusive"),
            v.count("warn"),
            v.count("block"),
            v.count("error"),
            f"{fail}/{n} ({lo:.0%}-{hi:.0%})" if n else "–",
            f"{statistics.median(ch):+.1f}%" if ch else "–",
            f"{min(ch):+.1f}% to {max(ch):+.1f}%" if ch else "–",
        ]

    for s in sets:
        j = json.loads(s.read_text(encoding="utf-8"))
        skip = affected_trials(j)
        t = [x for x in j["trials"] if x["trial"] not in skip]
        rows.append(row(j["set"], t, f"{len(t)}/{j['requested_trials']}"))
        if skip:
            rows.append(
                row(f"{j['set']} incl. affected", j["trials"], f"{len(j['trials'])} (all kept)")
            )
        for a in j.get("affected", []):
            lines.append(
                f"- {j['set']} trial {a['trial']} affected by competing work, left out of the "
                f"first row and replaced (result kept): {a['reason']}"
            )
        for rs in j.get("resumed", []):
            lines.append(
                f"- {j['set']}: run interrupted after trial {rs['after_trial']}, resumed at "
                f"{rs['at_utc']} ({rs['note']}); earlier trials kept"
            )
        for dd in j.get("discarded", []):
            lines.append(f"- {j['set']} trial {dd['trial']} discarded: {dd['discard_reason']}")
        if j.get("stopped"):
            lines.append(f"- {j['set']}: {j['stopped']}")
        for x in j["trials"]:
            if x["verdict"] == "error":
                lines.append(f"- {j['set']} trial {x['trial']} error: {x.get('reason')}")
    text = [
        "# Perf-gate validation (fresh runs, protocol in docs/gate-revision.md)",
        "",
        md_table(
            [
                "set",
                "counted trials/planned",
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
        "## Affected trials, interruptions, discards, errors",
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
    r.add_argument("--resume-note", help="continue a killed run of this set; why it stopped")
    c = sub.add_parser("calibrate-topk")
    c.add_argument("--ks", default="4,6,8,12")
    c.add_argument("--runs", type=int, default=3)
    m = sub.add_parser("mark-affected")
    m.add_argument("--set", required=True)
    m.add_argument("--trials", required=True, help="comma-separated trial numbers")
    m.add_argument("--reason", required=True)
    m.add_argument("--evidence", required=True, help="where the competing work is recorded")
    sub.add_parser("summarize")
    a = p.parse_args()
    if a.cmd == "run":
        n = a.trials or DEFAULT_TRIALS.get(a.set) or GRADED_TRIALS
        run(a.set, n, a.smoke, a.resume_note)
    elif a.cmd == "mark-affected":
        mark_affected(a.set, [int(x) for x in a.trials.split(",")], a.reason, a.evidence)
    elif a.cmd == "calibrate-topk":
        calibrate_topk([int(x) for x in a.ks.split(",")], a.runs)
    else:
        summarize()


if __name__ == "__main__":
    main()
