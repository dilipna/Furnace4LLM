"""Before a block of GPU measurements: are the frozen conditions met? Records them; exits 1 if not.

  uv run python bench/conditions.py --label "before V1 trial 15" [--expect-mhz 780] [--any-clock]

Checks (each one printed OK/FAIL, all written to bench/results/<date>/conditions/<utc>.json):
- power: on AC (the GPU drivers stop on battery; results on battery are not comparable);
- image: the lab vLLM container runs the image the kept validation trials recorded;
- code: no uncommitted change in the measurement code (gate, sandbox, harness, furnace-bench,
  the F1 fixture, the bench drivers), and the commit it runs from;
- clock: the GPU SM clock under a short load is within --tolerance-mhz of --expect-mhz, the
  clock every kept trial ran at (the driver picks it, it changes across reboots, and results
  at different clocks are not pooled); --any-clock records it without requiring it;
- machine: other running containers and the CPU busy share over 5 s with no load from us
  (recorded only; not a pass/fail condition).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time

from common import ROOT, power_state, results_dir, write_json

FROZEN_IMAGE = "sha256:8a69ffad015f138d7170c4ddc429e230a3bc1c1719f67e14324749df200a4b90"
MEASUREMENT_PATHS = [
    "packages/furnace/src/furnace/guardian",
    "packages/furnace/src/furnace/sandbox",
    "packages/furnace/src/furnace/evals",
    "packages/furnace/src/furnace/forge/harness.py",
    "packages/inference/src/furnace_bench",
    "fixtures/apps/support-rag-py",
    "bench/common.py",
    "bench/f1_scenarios.py",
    "bench/gate_validate.py",
    "bench/rq5.py",
    "bench/rq4.py",
    "bench/optimize.py",
    "packages/furnace/src/furnace/optimizer.py",
    "docker-compose.yml",
]


def _run(*cmd: str) -> str:
    try:
        return subprocess.run(  # noqa: S603 - fixed argv
            list(cmd), capture_output=True, text=True, timeout=30, cwd=ROOT
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--expect-mhz", type=float, default=780.0)
    p.add_argument("--tolerance-mhz", type=float, default=80.0)
    p.add_argument("--any-clock", action="store_true")
    p.add_argument("--lab", default="http://localhost:8100")
    a = p.parse_args()

    checks: dict[str, tuple[str, str]] = {}
    pw = power_state()
    checks["power"] = (
        ("OK", f"on AC, battery {pw.get('battery_pct')}%")
        if pw.get("on_ac")
        else ("FAIL", f"not on AC ({pw})")
    )

    img = _run("docker", "inspect", "furnace-vllm-1", "--format", "{{.Image}}")
    checks["image"] = (
        ("OK", img)
        if img == FROZEN_IMAGE
        else ("FAIL", f"{img or 'no container'} != {FROZEN_IMAGE}")
    )

    sha = _run("git", "rev-parse", "HEAD")
    dirty = [
        x for x in _run("git", "status", "--porcelain", "--", *MEASUREMENT_PATHS).splitlines() if x
    ]
    checks["code"] = (
        ("OK", f"measurement code clean at {sha[:7]}")
        if not dirty
        else ("FAIL", f"uncommitted measurement code: {dirty[:5]}")
    )

    import importlib.util

    spec = importlib.util.spec_from_file_location("preflight", ROOT / "scripts" / "preflight.py")
    assert spec and spec.loader
    preflight = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preflight)
    try:
        status, detail = preflight.check_gpu(a.lab, load=True)
    except Exception as exc:  # endpoint down, NVML missing: a failed check, not a crash
        status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
    m = re.search(r"median (\d+) MHz", detail)
    mhz = float(m.group(1)) if m else None
    if mhz is None:
        checks["clock"] = ("FAIL", f"no clock under load: {status} {detail}")
    elif a.any_clock or abs(mhz - a.expect_mhz) <= a.tolerance_mhz:
        checks["clock"] = ("OK" if status == "OK" else "FAIL", detail)
    else:
        checks["clock"] = (
            "FAIL",
            f"{detail}; the kept trials ran at {a.expect_mhz:.0f} MHz (+-{a.tolerance_mhz:.0f}): "
            "a different clock is a different condition (rerun with --any-clock only on purpose)",
        )

    containers = _run("docker", "ps", "--format", "{{.Names}}").splitlines()
    t0 = _system_busy()
    time.sleep(5)
    t1 = _system_busy()
    busy = (
        round(100 * (t1[0] - t0[0]) / (t1[1] - t0[1]), 1) if t0 and t1 and t1[1] > t0[1] else None
    )

    rec = {
        "label": a.label,
        "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": sha,
        "checks": {k: {"status": s, "detail": d} for k, (s, d) in checks.items()},
        "power": pw,
        "gpu_sm_mhz_under_load": mhz,
        "other_containers": [c for c in containers if not c.startswith("furnace-")],
        "cpu_busy_pct_5s_idle": busy,
    }
    out = results_dir("conditions") / f"{rec['at_utc'].replace(':', '')}.json"
    write_json(out, rec)
    for k, (s, d) in checks.items():
        print(f"{s:4s} {k:6s} {d}")
    print(f"     machine: CPU busy {busy}% over 5 s; other containers: {rec['other_containers']}")
    print(f"     recorded in {out.relative_to(ROOT)}")
    return 1 if any(s != "OK" for s, _ in checks.values()) else 0


def _system_busy() -> tuple[int, int] | None:
    from gate_validate import _system_times

    return _system_times()


if __name__ == "__main__":
    sys.exit(main())
