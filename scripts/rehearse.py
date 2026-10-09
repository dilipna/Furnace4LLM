"""Rehearse the local demo path in a real browser, timing every step (docs/demo.md).

  uv run python scripts/rehearse.py [--base http://localhost:3100] [--repo github.com/o/r]
                                    [--out docs/demo-shots/rehearsal-1] [--skip-gpu]

Steps: landing loads and its live panel connects -> GitHub scan to Blueprint -> graph path
trace -> /lab "Run it now" (real benchmark on the lab endpoint) -> /guard/r1_dynamic_head
"Run Guard on this PR" (real Guard run on the runner) -> /bench. Each step is timed from
the user's action to the moment the result is on screen, and screenshotted. The GitHub
App steps (Forge PR, R1 PR check run, repair PR) need the App and are not covered here.

Needs the stack running: API, web, cpu worker, runner, lab vLLM (or --skip-gpu).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:3100")
    p.add_argument("--repo", default="github.com/Azure-Samples/openai-chat-app-quickstart")
    p.add_argument("--out", default="docs/demo-shots/rehearsal")
    p.add_argument("--skip-gpu", action="store_true", help="skip Run it now and the Guard run")
    p.add_argument("--video", help="record a fallback screen video (.webm) into this directory")
    p.add_argument("--pace", type=float, default=None, help="seconds to dwell after each step")
    a = p.parse_args()
    pace = a.pace if a.pace is not None else (3.0 if a.video else 0.0)
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    def step(name: str, fn, page: Page) -> None:
        t0 = time.monotonic()
        ok, note = True, ""
        try:
            note = fn() or ""
        except Exception as exc:  # recorded, and the rehearsal continues
            ok, note = False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
        secs = time.monotonic() - t0
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32]
        shot = f"{len(rows) + 1:02d}-{slug}.png"
        if pace:
            page.wait_for_timeout(pace * 1000)  # let a viewer of the recording read the result
        page.screenshot(path=str(out / shot), full_page=False)
        rows.append({"step": name, "ok": ok, "seconds": round(secs, 1), "note": note, "shot": shot})
        print(f"{'ok ' if ok else 'BAD'} {secs:6.1f} s  {name}  {note}", flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        size = {"width": 1440, "height": 900}
        video_dir = ROOT / a.video if a.video else None
        ctx = browser.new_context(
            viewport=size,
            color_scheme="dark",
            record_video_dir=str(video_dir) if video_dir else None,
            record_video_size=size if video_dir else None,
        )
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        def landing() -> str:
            page.goto(a.base + "/", wait_until="load")
            page.get_by_text("Lab endpoint").first.wait_for(timeout=20_000)
            page.locator("text=/live · 1 s|lab offline/").first.wait_for(timeout=20_000)
            live = page.get_by_text("live · 1 s").count() > 0
            if pace:  # the hero replays, then the live panel, then back to the scan box
                page.wait_for_timeout(3000)
                page.locator("#lab-now").scroll_into_view_if_needed()
                page.wait_for_timeout(pace * 1500)
                page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
                page.wait_for_timeout(800)
            return "lab live" if live else "lab offline (recorded run shown)"

        def scan() -> str:
            page.get_by_placeholder("github.com/acme/support-bot").fill(a.repo)
            page.get_by_role("button", name="Scan").click()
            page.wait_for_url("**/scans/*", timeout=30_000)
            page.get_by_role("link", name="Graph →").wait_for(timeout=180_000)
            return page.url.rsplit("/", 1)[-1][:8]

        def graph() -> str:
            page.get_by_role("link", name="Graph →").click()
            page.wait_for_url("**/graph", timeout=30_000)
            node = page.locator('[role="button"][aria-label^="workflow"]').first
            node.wait_for(timeout=30_000)
            node.click()
            page.wait_for_timeout(1500)  # the trace animates hop by hop
            return f"{page.locator('[aria-label="Traced path, in order"] li').count()} nodes traced"

        def run_now() -> str:
            page.goto(a.base + "/lab", wait_until="load")
            page.get_by_role("button", name="Run it now").click()
            page.get_by_text("done · run").wait_for(timeout=240_000)
            return page.locator("text=/requests \\d+\\/\\d+/").first.inner_text()

        def guard() -> str:
            page.goto(a.base + "/guard/r1_dynamic_head", wait_until="load")
            page.locator("#guard-live").scroll_into_view_if_needed()
            page.get_by_role("button", name="Run Guard on this PR").click()
            page.get_by_text("waiting for the runner").or_(
                page.get_by_text("Impact ·")
            ).first.wait_for(timeout=30_000)
            page.locator("text=/s total/").first.wait_for(timeout=600_000)
            verdict = page.locator("section[aria-labelledby='guard-live'] .line-in").last
            return " ".join(verdict.inner_text().split())

        def bench() -> str:
            page.goto(a.base + "/bench", wait_until="load")
            page.get_by_role("heading").first.wait_for(timeout=20_000)
            return ""

        step("Landing + live panel", landing, page)
        step("Scan (GitHub) to Blueprint", scan, page)
        step("Graph path trace", graph, page)
        if not a.skip_gpu:
            step("Lab: Run it now", run_now, page)
            step("Guard run on R1", guard, page)
        step("FurnaceBench report", bench, page)
        video = page.video
        ctx.close()  # finalizes the recording
        if video and video_dir:
            final = video_dir / f"demo-{time.strftime('%Y-%m-%d-%H%M')}.webm"
            Path(video.path()).replace(final)
            print(f"video: {final.relative_to(ROOT).as_posix()}")
        browser.close()

    (out / "timings.json").write_text(json.dumps({"rows": rows, "page_errors": errors}, indent=2))
    print(
        f"\npage errors: {errors[:3] or 'none'}  ->  {out.relative_to(ROOT).as_posix()}/timings.json"
    )
    return 0 if all(r["ok"] for r in rows) and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
