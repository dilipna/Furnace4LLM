"""Shared helpers for the FurnaceBench drivers (bench/rq*.py, bench/report.py).

Every driver writes into bench/results/<date>/ (date = FURNACE_BENCH_DATE or today, UTC)
and records an environment manifest next to its numbers, so each figure in REPORT.md can
be traced to the command and machine that produced it.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "bench" / "results"
GROUND_TRUTH = ROOT / "bench" / "ground_truth"
EXTERNAL = ROOT / "bench" / ".cache" / "external"
F1 = ROOT / "fixtures" / "apps" / "support-rag-py"
SCENARIOS_DIR = ROOT / "fixtures" / "scenarios"
W1 = ROOT / "bench" / "results" / "2026-10-04-f1-quality" / "workload-f1-traces-qwen05b.yaml"

if str(SCENARIOS_DIR) not in sys.path:
    sys.path.insert(0, str(SCENARIOS_DIR))


def run_date() -> str:
    return os.environ.get("FURNACE_BENCH_DATE") or dt.datetime.now(dt.UTC).date().isoformat()


def results_dir(sub: str | None = None) -> Path:
    d = RESULTS / run_date()
    if sub:
        d = d / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def _out(cmd: list[str], cwd: Path | None = None) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, cwd=cwd)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_state() -> dict[str, Any]:
    sha = _out(["git", "rev-parse", "HEAD"], ROOT)
    dirty = _out(["git", "status", "--porcelain", "--untracked-files=no"], ROOT)
    return {"sha": sha, "dirty": bool(dirty)}


def gpu_info() -> dict[str, Any]:
    q = _out(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    if not q:
        return {}
    name, driver, mem = (x.strip() for x in q.splitlines()[0].split(","))
    return {"gpu": name, "driver": driver, "memory_mb": int(float(mem))}


def power_state() -> dict[str, Any]:
    """AC/battery state and the GPU power limit the driver enforces right now. On a laptop,
    battery mode caps the GPU (observed: 25 W, ~780 MHz vs 72 W, ~1,950 MHz on AC)."""
    state: dict[str, Any] = {"on_ac": None, "battery_pct": None, "gpu_enforced_power_limit_w": None}
    if platform.system() == "Windows":
        q = _out(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                '$b = Get-CimInstance Win32_Battery; if ($b) { "$($b.BatteryStatus),$($b.EstimatedChargeRemaining)" }',
            ]
        )
        if q:
            status, pct = q.split(",")
            # BatteryStatus 1 = discharging; 2 = on AC; 3-9 = charging/charged variants.
            state["on_ac"] = status.strip() != "1"
            state["battery_pct"] = int(pct)
        else:
            state["on_ac"] = True  # no battery: a desktop
    elif Path("/sys/class/power_supply").exists():
        online = list(Path("/sys/class/power_supply").glob("*/online"))
        if online:
            state["on_ac"] = any(p.read_text().strip() == "1" for p in online)
    lim = _out(["nvidia-smi", "--query-gpu=enforced.power.limit", "--format=csv,noheader,nounits"])
    if lim:
        with contextlib.suppress(ValueError):
            state["gpu_enforced_power_limit_w"] = float(lim.splitlines()[0])
    return state


def require_ac_power(allow_battery: bool = False) -> dict[str, Any]:
    """GPU drivers call this first: measurements on battery are not comparable."""
    st = power_state()
    if st["on_ac"] is False and not allow_battery:
        raise SystemExit(
            f"refusing to benchmark on battery ({st['battery_pct']}% left, GPU power limit "
            f"{st['gpu_enforced_power_limit_w']} W). Plug in AC power, or pass --allow-battery "
            "to record a labeled battery run."
        )
    return st


def manifest(**extra: Any) -> dict[str, Any]:
    return {
        "date": run_date(),
        "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "git": git_state(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        **gpu_info(),
        "power": power_state(),
        "argv": sys.argv,
        **extra,
    }


def write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def f1_questions() -> list[str]:
    facts = read_json(F1 / "docs" / "facts.json")
    return [f["question"] for f in facts]


def md_table(header: list[str], rows: list[list[Any]], align: str | None = None) -> str:
    align = align or "l" + "r" * (len(header) - 1)
    sep = ["---:" if a == "r" else "---" for a in align]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    lines += ["| " + " | ".join("–" if c is None else str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def fmt(x: float | None, nd: int = 1) -> str:
    return "–" if x is None else f"{x:,.{nd}f}"
