"""Browser and link verification against the unpublished static export."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:4010")
    parser.add_argument("--out", type=Path, default=Path("dist/site-verification.json"))
    parser.add_argument("--screenshots", type=Path, default=Path("dist/site-screenshots"))
    parser.add_argument("--browser-executable", type=Path)
    args = parser.parse_args()
    assert args.url.startswith("http://127.0.0.1:"), "Only a local preview is tested"
    args.screenshots.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(urllib.request.urlopen(args.url + "/downloads/installer.json").read())  # noqa: S310 -- loopback only
    checks = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=str(args.browser_executable) if args.browser_executable else None
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.url)
        expect(
            page.get_by_role("heading", name="You build the model.", exact=False)
        ).to_be_visible()
        expect(page.locator("main")).to_contain_text("free infrastructure starter kit")
        expect(page.locator("main")).to_contain_text("proposed at $20/month")
        checks["researcher_product_and_proposed_service_clear"] = True
        button = page.get_by_role("link", name="Download Furnace", exact=False)
        expect(button).to_have_attribute("href", "/downloads/" + metadata["file"])
        checks["windows_download_target"] = True
        page.get_by_text("Version, build date & SHA-256").click()
        expect(page.get_by_test_id("checksum")).to_have_text(metadata["sha256"])
        checks["checksum_matches_build_metadata"] = True
        with page.expect_download() as downloading:
            button.click()
        download = downloading.value
        downloaded = args.screenshots / download.suggested_filename
        download.save_as(downloaded)
        checks["downloaded_bytes_match_checksum"] = (
            hashlib.sha256(downloaded.read_bytes()).hexdigest() == metadata["sha256"]
        )
        downloaded.unlink()
        # Return to the clean first screen for actual desktop/mobile captures.
        page.get_by_text("Version, build date & SHA-256").click()
        page.screenshot(path=str(args.screenshots / "home-desktop.png"))
        page.screenshot(path=str(args.screenshots / "home-desktop-full.png"), full_page=True)
        links = set()
        for route in (
            "/",
            "/start",
            "/demo",
            "/docs",
            "/security",
            "/pricing",
            "/releases",
            "/faq",
            "/support",
            "/about",
            "/privacy",
            "/terms",
            "/earlier-work",
            "/examples/documents",
        ):
            response = page.goto(args.url + route)
            assert response is not None and response.status == 200, route
            expect(page.locator("h1")).to_be_visible()
            assert page.locator(".product-doc, .product-hero").count() == 1, route
            for element in page.locator("a[href]").all():
                href = element.get_attribute("href") or ""
                if href.startswith("/") and not href.startswith("//"):
                    links.add(href.split("#")[0])
            for image in page.locator("img").all():
                image.scroll_into_view_if_needed()
                expect(image).to_have_js_property("complete", True)
                assert image.evaluate("img => img.naturalWidth > 0"), (
                    route,
                    image.get_attribute("src"),
                )
        for href in sorted(links):
            response = context.request.get(args.url + href)
            assert response.ok, (href, response.status)
        checks["local_links_and_images"] = True
        page.goto(args.url + "/examples/documents")
        expect(
            page.get_by_role("heading", name="A document. An answer. Its checks.")
        ).to_be_visible()
        if page.locator("video").count() == 0:
            expect(
                page.get_by_role("heading", name="Recording not staged in this build")
            ).to_be_visible()
        checks["document_recording_status_honest"] = True
        page.goto(args.url + "/researchers/tour")
        page.get_by_role("button", name="3. Explore").click()
        expect(page.get_by_role("heading", name="3. Explore the guided example")).to_be_visible()
        checks["recorded_tour"] = True
        page.get_by_role("link", name="Docs", exact=True).first.click()
        expect(page).to_have_url(args.url + "/docs")
        page.get_by_role("link", name="Tour", exact=True).first.click()
        expect(
            page.get_by_role("heading", name="A look inside your local workspace.")
        ).to_be_visible()
        checks["header_navigation"] = True
        page.get_by_role("button", name="Switch color theme").click()
        expect(page.locator(".download-site")).to_have_attribute("data-theme", "dark")
        checks["theme_toggle"] = True
        page.goto(args.url + "/security")
        expect(page.get_by_role("heading", name="Manipulated documents")).to_be_visible()
        expect(page.locator("main")).to_contain_text("no internet route")
        page.goto(args.url + "/faq")
        expect(
            page.get_by_role("heading", name="What if a document tries to instruct the AI?")
        ).to_be_visible()
        expect(page.locator("main")).to_contain_text("These mitigations are incomplete")
        checks["manipulated_document_limits_disclosed"] = True

        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            color_scheme="light",
            user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/134.0.0.0 Mobile Safari/537.36",
        )
        mobile_page = mobile.new_page()
        mobile_page.goto(args.url)
        expect(mobile_page.get_by_role("link", name="See download options")).to_be_visible()
        assert mobile_page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            "Mobile overflow"
        )
        mobile_page.screenshot(path=str(args.screenshots / "home-mobile.png"))
        mobile_page.screenshot(path=str(args.screenshots / "home-mobile-full.png"), full_page=True)
        checks["mobile_layout"] = True
        mac = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)")
        mac_page = mac.new_page()
        mac_page.goto(args.url)
        options = mac_page.get_by_role("link", name="See download options")
        expect(options).to_be_visible()
        options.click()
        expect(mac_page.locator("#platforms")).to_have_attribute("open", "")
        checks["unsupported_os_options"] = True
        checks["no_browser_errors"] = not errors
        browser.close()
    assert all(checks.values()), checks
    record = {
        "schema": "furnace-download-site-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "installer_commit": metadata["commit"],
        "checks": checks,
        "local_links_checked": len(links),
        "result": "passed",
        "model_inference": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
