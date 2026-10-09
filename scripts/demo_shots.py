"""Screenshot the demo pages (desktop) into docs/demo-shots/ as the offline fallback.

  uv run python scripts/demo_shots.py [--base http://localhost:3000] [--scan SCAN_ID] [--mobile]

Fails loudly if a page errors, logs a console error, or overflows horizontally.
Pages hold live SSE streams open, so "network idle" never happens: each page is captured
after load plus a fixed settle time (--settle) for the first stream events to render.
--mobile captures at 390x844 into docs/demo-shots/mobile/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "demo-shots"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:3000")
    p.add_argument("--scan", help="scan id: also capture its Blueprint and graph")
    p.add_argument("--mobile", action="store_true", help="390 px wide viewport")
    p.add_argument("--settle", type=float, default=3.0, help="seconds after load")
    p.add_argument("--only", help="comma-separated paths to capture instead of the default set")
    a = p.parse_args()
    pages = ["/", "/lab", "/guard", "/guard/r1_dynamic_head", "/evals", "/bench", "/pricing"]
    if a.scan:
        pages += [f"/scans/{a.scan}", f"/scans/{a.scan}/graph"]
    if a.only:
        pages = a.only.split(",")
    out = OUT / "mobile" if a.mobile else OUT
    out.mkdir(parents=True, exist_ok=True)
    viewport = {"width": 390, "height": 844} if a.mobile else {"width": 1440, "height": 900}
    problems = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=viewport, color_scheme="dark")
        for path in pages:
            page = ctx.new_page()
            errors: list[str] = []
            page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
            resp = page.goto(a.base + path, wait_until="load", timeout=120_000)
            page.wait_for_timeout(a.settle * 1000)
            name = (path.strip("/").replace("/", "_") or "home") + ".png"
            page.screenshot(path=str(out / name), full_page=True)
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            status = resp.status if resp else 0
            ok = status == 200 and not errors and not overflow
            problems += not ok
            print(
                f"{'ok ' if ok else 'BAD'} {path} -> {out.relative_to(OUT.parents[1]).as_posix()}/{name} (HTTP {status}, overflow={overflow}, errors={errors[:3]})"
            )
            page.close()
        browser.close()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
