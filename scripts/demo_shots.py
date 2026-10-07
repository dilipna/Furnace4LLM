"""Screenshot the demo pages (desktop) into docs/demo-shots/ as the offline fallback.

  uv run python scripts/demo_shots.py [--base http://localhost:3000] [--scan SCAN_ID]

Fails loudly if a page errors, logs a console error, or overflows horizontally.
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
    a = p.parse_args()
    pages = ["/", "/lab", "/guard", "/guard/r1_dynamic_head", "/evals", "/bench", "/pricing"]
    if a.scan:
        pages += [f"/scans/{a.scan}", f"/scans/{a.scan}/graph"]
    OUT.mkdir(parents=True, exist_ok=True)
    problems = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        for path in pages:
            page = ctx.new_page()
            errors: list[str] = []
            page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
            resp = page.goto(a.base + path, wait_until="networkidle", timeout=120_000)
            name = (path.strip("/").replace("/", "_") or "home") + ".png"
            page.screenshot(path=str(OUT / name), full_page=True)
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            status = resp.status if resp else 0
            ok = status == 200 and not errors and not overflow
            problems += not ok
            print(
                f"{'ok ' if ok else 'BAD'} {path} -> docs/demo-shots/{name} (HTTP {status}, overflow={overflow}, errors={errors[:3]})"
            )
            page.close()
        browser.close()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
