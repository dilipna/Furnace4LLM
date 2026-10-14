"""Smoke-test a Furnace deployment (hosted, or the production image run locally).

  uv run python scripts/smoke_hosted.py --api https://furnace-api-XXXX.onrender.com \
      --web https://furnace-XXXX.vercel.app [--scan github.com/peterw/llamav2-chat] [--out FILE.md]
  uv run python scripts/smoke_hosted.py --web https://furnace-XXXX.vercel.app   # recorded-only site

Without --api, the web deployment is checked as a recorded-only site (NEXT_PUBLIC_RECORDED_ONLY,
no API, no runner): every page renders its recorded results, the recording streams (range
requests), live controls say they are unavailable, nothing under /api answers, and the pilot
contact link is present.

With --api, checks what docs/deploy.md promises a public deployment does and refuses. It only reads,
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
    p.add_argument("--api", help="API base URL, no trailing slash; omit for a recorded-only site")
    p.add_argument("--web", help="web base URL (Vercel); its /api rewrite is checked too")
    p.add_argument("--scan", help="also run one public GitHub scan of this repo, end to end")
    p.add_argument("--wake", type=float, default=120, help="seconds to wait for a sleeping API")
    p.add_argument("--out", help="write the results as a markdown table to this file")
    p.add_argument(
        "--contact",
        default="https://www.linkedin.com/in/dilip-n-ab1091417/",
        help="the pilot contact URL the site was built with (NEXT_PUBLIC_CONTACT_URL)",
    )
    a = p.parse_args()
    if not a.api and not a.web:
        p.error("give --api, --web, or both")
    for u in (a.api or "https://", a.web or "https://"):
        if not u.startswith(("http://", "https://")):
            p.error(f"{u}: only http:// and https:// URLs")
    rows: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        rows.append((name, ok, detail))
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}", flush=True)

    if not a.api:
        recorded_site(a.web.rstrip("/"), check, a.contact)
        return report(a, rows, f"web `{a.web}` (recorded-only, no API)")
    api = a.api.rstrip("/")

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

    return report(a, rows, f"API `{api}`" + (f", web `{a.web}`" if a.web else ""))


def report(a: argparse.Namespace, rows: list[tuple[str, bool, str]], target: str) -> int:
    passed = all(ok for _, ok, _ in rows)
    if a.out:
        lines = [
            f"# Smoke test, {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
            "",
            target,
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


def get(url: str, headers: dict[str, str] | None = None) -> tuple[int, str, dict[str, str], str]:
    """(status, final URL, headers, body) without raising on 4xx/5xx; media bodies are skipped."""
    req = urllib.request.Request(url, headers=headers or {})  # noqa: S310 - operator's URL
    try:
        with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            media = hdrs.get("content-type", "").startswith(("video/", "image/"))
            body = "" if media else r.read().decode("utf-8", "replace")
            return r.status, r.geturl(), hdrs, body
    except urllib.error.HTTPError as e:
        return e.code, url, {k.lower(): v for k, v in e.headers.items()}, ""


def recorded_site(web: str, check: Any, contact: str) -> None:
    pages = (
        ("/", ["RECORDED RUN", "/demo"]),
        (
            "/demo",
            [
                "Demo · recorded",
                "furnace-demo.webm",
                "furnace-demo.mp4",
                "/pull/2",
                "signed event queued a new Guard run",
            ],
        ),
        ("/pilot", ["Design-partner pilot", "recorded-only site", "Scanning is not available"]),
        ("/bench", ["2026-10-12-gate-validation"]),
        ("/guard", ["r1_dynamic_head"]),
        ("/guard/r1_dynamic_head", ["Live runs are turned off", "Live runs off here"]),
        ("/lab", ["no lab on this site", "Lab GPU offline"]),
        ("/evals", ["recorded-only site does not have"]),
    )
    for path, must in pages:
        s, _, _, html = get(web + path)
        missing = [m for m in must if m.lower() not in html.lower()]
        check(
            f"page {path}",
            s == 200 and not missing,
            f"{s}" + (f", missing {missing}" if missing else ""),
        )
    s, final, _, html = get(web + "/pricing")
    # a static page's redirect() is served as a meta refresh plus a client-side redirect
    moved = final.rstrip("/").endswith("/pilot") or 'content="1;url=/pilot' in html
    check("/pricing redirects to /pilot", s == 200 and moved, final)
    s, _, _, html = get(web + "/pilot")
    check("pilot contact link", f'href="{contact}"' in html, contact)
    for path, kind in (
        ("/demo/furnace-demo.webm", "video/webm"),
        ("/demo/furnace-demo.mp4", "video/mp4"),
    ):
        s, _, h, _ = get(web + path, {"Range": "bytes=0-1023"})
        check(
            f"recording {path} streams",
            s == 206 and h.get("content-type", "").startswith(kind) and "content-range" in h,
            f"{s} {h.get('content-type')} {h.get('content-range')}",
        )
    s, _, h, _ = get(web + "/demo/poster.png")
    check("video poster", s == 200 and h.get("content-type") == "image/png", f"{s}")
    s, _, _, body = get(web + "/recorded/live-recorded.json")
    check("recorded lab telemetry", s == 200 and '"series"' in body, f"{s}")
    for method, path in (
        ("POST", "/api/guard/runs"),
        ("POST", "/api/public/scans"),
        ("POST", "/api/live/bench"),
        ("GET", "/api/live/status"),
        ("GET", "/healthz"),
    ):
        try:
            st, _ = call(method, web + path, {} if method == "POST" else None)
        except OSError as e:
            st = str(e)
        check(f"no API: {method} {path}", st in (404, 405), f"{st}")
    s, _, _, _ = get(web + "/no-such-page")
    check("unknown page is a 404", s == 404, f"{s}")


if __name__ == "__main__":
    sys.exit(main())
