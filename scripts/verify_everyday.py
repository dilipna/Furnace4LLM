"""Real browser + local HTTP + scripted adapter; no real model or Docker proof claimed."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from furnace_api.desktop import DesktopService  # noqa: E402

from apps.api.tests.test_everyday import (  # noqa: E402 -- test-only browser harness
    privacy_double,
    text_pdf,
)
from apps.api.tests.test_studio_managed import ANSWERS, TOKEN, build, ready_project  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-executable", type=Path)
    parser.add_argument("--out", type=Path, default=Path("dist/everyday-browser"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="furnace-document-browser-"))
    app, fake = build(root)
    service = DesktopService(root / "ws")
    service.server.config.app = app
    service.start()
    record = {
        "schema": "furnace-everyday-browser-v1",
        "at": datetime.now(UTC).isoformat(),
        "execution": "scripted Python test adapter over actual loopback HTTP; not an LLM",
        "result": "failed",
        "checks": {},
    }
    try:
        with httpx.Client(
            base_url=service.url, headers={"x-furnace-session": TOKEN}, timeout=30
        ) as client:
            pid = ready_project(client)
            privacy_double(app, fake, pid)
            marker = "Review meeting on 2026-12-03. Owner: Maya."
            ANSWERS[marker] = "Maya owns the review meeting on 2026-12-03."
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=str(args.browser_executable)
                    if args.browser_executable
                    else None
                )
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors, requests = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url))
                page.goto(service.url + "/#session=" + TOKEN)
                expect(
                    page.get_by_role("heading", name="A little help.", exact=False)
                ).to_be_visible()
                expect(page.locator("#model-status")).to_contain_text("ready", timeout=30000)
                page.screenshot(path=str(args.out / "app-desktop.png"), full_page=True)
                data = base64.b64encode(text_pdf(marker)).decode()
                transfer = page.evaluate_handle(
                    "data => {const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0)); const dt=new DataTransfer();dt.items.add(new File([bytes],'review-note.pdf',{type:'application/pdf'}));return dt;}",
                    data,
                )
                page.locator("#document-box").dispatch_event("drop", {"dataTransfer": transfer})
                expect(page.locator("#document-info")).to_contain_text(
                    "review-note.pdf", timeout=30000
                )
                record["checks"]["real_pdf_drop_and_local_extraction"] = True
                with page.expect_response(
                    lambda r: "/everyday/projects/" in r.url and r.url.endswith("/answer"),
                    timeout=60000,
                ) as response:
                    page.get_by_role("button", name="Summarise", exact=True).click()
                answer = response.value.json()
                assert response.value.status == 200 and answer["processing"]["model_requests"] == 1
                expect(page.locator(".output")).to_have_text(ANSWERS[marker])
                record["checks"]["actual_adapter_execution"] = True
                page.locator(".receipt > summary").click()
                expect(page.locator(".receipt")).to_contain_text(
                    "test adapter, not real Docker proof"
                )
                expect(page.locator(".receipt")).to_contain_text("not proof about every program")
                page.get_by_text("Model identity and technical details", exact=True).click()
                expect(page.locator(".receipt")).to_contain_text(
                    answer["receipt"]["model"]["weights_sha256"]
                )
                record["checks"]["receipt_and_limits_visible"] = True
                page.screenshot(path=str(args.out / "answer-receipt.png"), full_page=True)
                # Clearing is a user action, and must remove both source text and answer.
                page.get_by_role("button", name="New conversation", exact=False).click()
                expect(page.locator(".answer")).to_have_count(0)
                record["checks"]["clear_removes_conversation"] = True
                mobile = browser.new_page(
                    viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
                )
                mobile.goto(service.url + "/#session=" + TOKEN)
                expect(
                    mobile.get_by_role("heading", name="A little help.", exact=False)
                ).to_be_visible()
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
                mobile.screenshot(path=str(args.out / "app-mobile.png"), full_page=True)
                record["checks"]["mobile_no_overflow"] = True
                assert not errors, errors
                assert all(url.startswith(service.url + "/") for url in requests), requests
                record["checks"]["no_external_requests_or_browser_errors"] = True
                browser.close()
            record["result"] = "passed"
    finally:
        record["quit_and_lease_released"] = service.stop()
        (args.out / "record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    assert record["result"] == "passed" and record["quit_and_lease_released"]
    print(args.out / "record.json")


if __name__ == "__main__":
    main()
