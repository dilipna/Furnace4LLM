"""Stage pre-flight: is everything the demo needs up, and is the GPU at full clock?

  uv run python scripts/preflight.py [--web http://localhost:3100] [--api http://localhost:8010]
                                     [--lab http://localhost:8100] [--owner dilipna] [--load]

Prints one line per check (OK / WARN / FAIL) and exits 1 if any check FAILs. --load sends 16
short requests to the lab endpoint while sampling NVML, so the reported clock is the clock
under load (the number to say on stage), not the idle clock.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
Result = tuple[str, str]  # (OK|WARN|FAIL, detail)


def _get(url: str, timeout: float = 5) -> httpx.Response:
    return httpx.get(url, timeout=timeout)


def check_power() -> Result:
    if platform.system() != "Windows":
        return "OK", "not Windows: skipped"
    # Windows 11 "power mode" is an overlay on the (usually only) Balanced plan.
    ps = (
        "(Get-CimInstance -ClassName BatteryStatus -Namespace root/wmi | Select -First 1).PowerOnline;"
        "(Get-ItemProperty 'HKLM:/SYSTEM/CurrentControlSet/Control/Power/User/PowerSchemes')"
        ".ActiveOverlayAcPowerScheme"
    )
    out = subprocess.run(  # noqa: S603 - fixed argv
        ["powershell", "-NoProfile", "-Command", ps],  # noqa: S607 - Windows built-in
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.split()
    on_ac = out[0] == "True" if out else None
    overlay = out[1] if len(out) > 1 else ""
    mode = {
        "ded574b5-45a0-4f42-8737-46345c09c238": "Best performance",
        "961cc777-2547-4f9d-8174-7d86181b8a7a": "Best power efficiency",
        "00000000-0000-0000-0000-000000000000": "Balanced",
    }.get(overlay, overlay or "unknown")
    if on_ac is False:
        return "FAIL", "on battery: the GPU driver refuses vLLM on battery; plug in"
    return ("OK" if mode == "Best performance" else "WARN"), f"on AC, Windows power mode '{mode}'"


def check_api(api: str) -> Result:
    h = _get(f"{api}/healthz").json()
    return ("OK", "database reachable") if h.get("db") else ("FAIL", "API up, database down")


def check_lab(lab: str) -> Result:
    models = _get(f"{lab}/v1/models").json()
    return "OK", f"serving {[m['id'] for m in models['data']]}"


def check_web(web: str) -> Result:
    bad = [
        p
        for p in ("/", "/lab", "/guard/r1_dynamic_head", "/bench")
        if _get(web + p, 60).status_code != 200
    ]
    return (
        ("FAIL", f"HTTP errors on {bad}")
        if bad
        else ("OK", "/, /lab, /guard/r1_dynamic_head, /bench")
    )


def check_stream(web: str) -> Result:
    """A live sample must reach a gzip-accepting client through the web proxy within 6 s."""
    t0 = time.monotonic()
    with httpx.stream(
        "GET", f"{web}/api/live/telemetry", headers={"Accept-Encoding": "gzip"}, timeout=8
    ) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                d = json.loads(line[6:])
                state = "lab live" if d.get("online") else "lab offline (recorded run shown)"
                return (
                    "OK" if d.get("online") else "WARN"
                ), f"{state}, first sample in {time.monotonic() - t0:.1f} s"
            if time.monotonic() - t0 > 6:
                break
    return "FAIL", "no live sample through the web proxy within 6 s (proxy buffering?)"


def check_runners(api: str) -> Result:
    rs = [r for r in _get(f"{api}/api/runners").json() if r["online"]]
    queues = {q for r in rs for q in r["queues"]}
    missing = [q for q in ("cpu", "runner") if q not in queues]
    if missing:
        hint = {"cpu": "uv run poe worker", "runner": "uv run poe runner"}
        return "FAIL", "offline: " + ", ".join(f"{q} ({hint[q]})" for q in missing)
    return "OK", "scan worker and Guard runner online"


def check_recorded(api: str) -> Result:
    r = _get(f"{api}/api/live/recorded", 20)
    return (
        ("OK", f"fallback ready: {r.json()['source']}")
        if r.status_code == 200
        else ("FAIL", "no recorded run")
    )


def check_gpu(lab: str, load: bool) -> Result:
    try:
        import pynvml
    except ImportError:
        return "WARN", "nvidia-ml-py not installed"
    pynvml.nvmlInit()
    h = pynvml.nvmlDeviceGetHandleByIndex(0)

    def clock() -> tuple[int, float]:
        return (
            pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM),
            pynvml.nvmlDeviceGetPowerUsage(h) / 1000,
        )

    if not load:
        c, w = clock()
        return "OK", f"idle {c} MHz, {w:.1f} W (use --load for the clock under load)"

    samples: list[tuple[int, float]] = []
    reasons = 0
    get_reasons = (
        getattr(pynvml, "nvmlDeviceGetCurrentClocksEventReasons", None)
        or pynvml.nvmlDeviceGetCurrentClocksThrottleReasons
    )

    async def go() -> None:
        async with httpx.AsyncClient(timeout=60) as c:
            body = {"model": "lab", "max_tokens": 128, "ignore_eos": True,
                    "messages": [{"role": "user", "content": "Count slowly from one."}]}  # fmt: skip

            async def one() -> None:
                (await c.post(f"{lab}/v1/chat/completions", json=body)).raise_for_status()

            async def sample() -> None:
                nonlocal reasons
                for _ in range(40):
                    samples.append(clock())
                    reasons |= get_reasons(h)
                    await asyncio.sleep(0.1)

            await asyncio.gather(sample(), *(one() for _ in range(16)))

    asyncio.run(go())
    busy = [s for s in samples if s[1] > 15] or samples
    mhz = sorted(s[0] for s in busy)[len(busy) // 2]
    watts = max(s[1] for s in busy)
    # NVML clock-event reason bits: 0x1 idle, 0x4 SW power cap, 0x8 HW slowdown,
    # 0x20 SW thermal, 0x40 HW thermal, 0x80 HW power brake
    names = {0x1: "idle", 0x4: "power limit", 0x8: "HW slowdown", 0x20: "SW thermal",
             0x40: "HW thermal", 0x80: "power brake"}  # fmt: skip
    active = [n for bit, n in names.items() if reasons & bit] or ["none"]
    throttled = bool(reasons & (0x8 | 0x20 | 0x40 | 0x80))
    status = "WARN" if throttled else "OK"
    why = (
        "throttled: say so when showing latency"
        if throttled
        else "not throttled (the driver picks this clock for this load)"
    )
    return (
        status,
        f"under load: median {mhz} MHz, peak {watts:.0f} W, reasons {'+'.join(active)}; {why}",
    )


def check_github(owner: str | None) -> Result:
    out = subprocess.run(
        [sys.executable, "-m", "furnace.cli", "gh-check"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=ROOT,
    )
    text = (out.stdout + out.stderr).strip().splitlines()
    if out.returncode != 0:
        msg = text[-1] if text else "gh-check failed"
        return "FAIL", msg if "github-app.md" in msg else f"{msg} (docs/github-app.md)"
    detail = text[-1] if text else "ok"
    if owner:
        r = _get(f"https://api.github.com/repos/{owner}/furnace-demo-f1", 10)
        if r.status_code != 200:
            return "FAIL", f"github.com/{owner}/furnace-demo-f1 is not public ({r.status_code})"
    return "OK", detail


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--web", default="http://localhost:3100")
    p.add_argument("--api", default="http://localhost:8010")
    p.add_argument("--lab", default="http://localhost:8100")
    p.add_argument("--owner", default=None, help="GitHub owner of furnace-demo-f1")
    p.add_argument("--load", action="store_true", help="measure the GPU clock under load")
    a = p.parse_args()
    checks: list[tuple[str, Callable[[], Result]]] = [
        ("power", check_power),
        ("api + database", lambda: check_api(a.api)),
        ("lab vLLM", lambda: check_lab(a.lab)),
        ("GPU clock", lambda: check_gpu(a.lab, a.load)),
        ("web pages", lambda: check_web(a.web)),
        ("live stream via web", lambda: check_stream(a.web)),
        ("worker + runner", lambda: check_runners(a.api)),
        ("offline fallback", lambda: check_recorded(a.api)),
        ("GitHub App", lambda: check_github(a.owner)),
    ]
    worst = "OK"
    for name, fn in checks:
        try:
            status, detail = fn()
        except Exception as exc:  # every failure is reported, the rest still run
            status, detail = "FAIL", f"{type(exc).__name__}: {str(exc)[:160]}"
        if status == "FAIL" or (status == "WARN" and worst == "OK"):
            worst = status
        print(f"{status:<4}  {name:<20} {detail}", flush=True)
    print(f"\npre-flight: {worst}")
    return 1 if worst == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
