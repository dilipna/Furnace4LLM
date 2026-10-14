"""Smoke-test a Furnace deployment (hosted, or the production image run locally).

  uv run python scripts/smoke_hosted.py --api https://furnace-api-XXXX.onrender.com \
      --web https://furnace-XXXX.vercel.app [--scan github.com/peterw/llamav2-chat] [--out FILE.md]

Checks what docs/deploy.md promises a public deployment does and refuses. It only reads,
except two requests that must be refused and one optional public scan (--scan). Exit code 0
only if every check passed. A free Render API sleeps when idle: the first request can take
about a minute, so the health check waits up to --wake seconds.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any


def call(method: str, url: str, body: dict | None = None, timeout: float = 30) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - http(s) only, checked in main()
    if data is not None:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URLs given by the operator
            raw = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8", "replace"), e.code
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api", required=True, help="API base URL, no trailing slash")
    p.add_argument("--web", help="web base URL (Vercel); its /api rewrite is checked too")
    p.add_argument("--scan", help="also run one public GitHub scan of this repo, end to end")
    p.add_argument("--wake", type=float, default=120, help="seconds to wait for a sleeping API")
    p.add_argument("--out", help="write the results as a markdown table to this file")
    a = p.parse_args()
    for u in (a.api, a.web or "https://"):
        if not u.startswith(("http://", "https://")):
            p.error(f"{u}: only http:// and https:// URLs")
    api = a.api.rstrip("/")
    rows: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        rows.append((name, ok, detail))
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}", flush=True)

    t0, health = time.monotonic(), None
    while time.monotonic() - t0 < a.wake:
        try:
            s, health = call("GET", f"{api}/healthz", timeout=60)
            if s == 200:
                break
        except OSError:
            pass
        time.sleep(5)
    check(
        "health",
        isinstance(health, dict) and health.get("db") is True,
        f"{health} after {time.monotonic() - t0:.0f} s",
    )

    s, runners = call("GET", f"{api}/api/runners")
    leaky = (
        [r for r in runners if not str(r.get("id", "")).startswith("runner-")]
        if isinstance(runners, list)
        else ["?"]
    )
    extra = (
        [r for r in runners if set(r.get("capabilities", {})) - {"gpu", "docker"}]
        if isinstance(runners, list)
        else []
    )
    check(
        "runner list hides host details",
        s == 200 and not leaky and not extra,
        f"{len(runners) if isinstance(runners, list) else runners} runners",
    )

    s, st = call("GET", f"{api}/api/live/status")
    check(
        "live lab off, visitor runs off",
        s == 200 and st.get("live_lab") is False and st.get("public_runs") is False,
        str(st),
    )

    s, b = call("POST", f"{api}/api/guard/runs", {"scenario": "r1_dynamic_head"})
    check("visitor Guard run refused", s == 403, f"{s} {b}")

    s, b = call("POST", f"{api}/api/public/scans", {"kind": "fixture", "value": "support-rag-py"})
    check("fixture scan refused (dev only)", s == 404, f"{s}")

    s, b = call("POST", f"{api}/api/labels", {"id": "smoke", "grounded": True})
    check("labeling read-only", s == 403, f"{s}")

    s, camps = call("GET", f"{api}/api/bench/campaigns")
    names = (
        {
            c["name"]
            for c in camps
            if "gate_validation" in c.get("available", []) or "rq5" in c.get("available", [])
        }
        if isinstance(camps, list)
        else set()
    )
    check(
        "recorded results present",
        "2026-10-12-gate-validation" in names,
        ", ".join(sorted(names))[:120],
    )

    if a.web:
        web = a.web.rstrip("/")
        for path, must in (
            ("/", "RECORDED RUN"),
            ("/pilot", "Design-partner pilot"),
            ("/guard/r1_dynamic_head", "r1_dynamic_head"),
            ("/bench", ""),
        ):
            try:
                with urllib.request.urlopen(web + path, timeout=90) as r:  # noqa: S310
                    html = r.read().decode("utf-8", "replace")
                    ok = r.status == 200 and must.lower() in html.lower()
                    check(
                        f"web {path}",
                        ok,
                        f"{r.status}" + (f", has '{must}'" if must and ok else ""),
                    )
            except urllib.error.HTTPError as e:
                check(f"web {path}", False, f"{e.code}")
        s, b = call("GET", f"{web}/api/live/status")
        check(
            "web /api rewrite reaches the API",
            s == 200 and isinstance(b, dict) and "public_runs" in b,
            f"{s}",
        )

    if a.scan:
        s, b = call("POST", f"{api}/api/public/scans", {"kind": "github", "value": a.scan})
        sid = b.get("scan_id") if isinstance(b, dict) else None
        status = None
        for _ in range(60):
            if not sid:
                break
            _, sc = call("GET", f"{api}/api/scans/{sid}")
            status = sc.get("status") if isinstance(sc, dict) else None
            if status in ("succeeded", "failed"):
                break
            time.sleep(3)
        check(f"public scan {a.scan}", status == "succeeded", f"{s} scan {sid} {status}")

    passed = all(ok for _, ok, _ in rows)
    if a.out:
        lines = [
            f"# Smoke test, {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
            "",
            f"API `{api}`" + (f", web `{a.web}`" if a.web else ""),
            "",
            "| check | result | detail |",
            "|---|---|---|",
            *[
                f"| {n} | {'pass' if ok else '**fail**'} | {d.replace('|', '/')} |"
                for n, ok, d in rows
            ],
            "",
            f"Overall: {'pass' if passed else 'FAIL'}",
        ]
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print("\nall checks passed" if passed else "\nSOME CHECKS FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
