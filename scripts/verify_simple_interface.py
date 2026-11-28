"""Check public setup and local Studio in isolated headless browsers, not user tabs."""

from __future__ import annotations

import argparse
import faulthandler
import gc
import json
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from furnace.starter import export_starter
from furnace_api.studio import create_app
from playwright.sync_api import expect, sync_playwright
from studio_connector_checks import verify_connector


def public_journey(site: str, channel: str | None, screenshots: Path) -> dict:
    errors = []
    writes = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "request",
            lambda request: writes.append(request.url) if request.method == "POST" else None,
        )
        try:
            page.goto(site, wait_until="networkidle", timeout=120000)
            expect(
                page.get_by_role("heading", name="What would you like to build?")
            ).to_be_visible()
            page.screenshot(path=str(screenshots / "public-home-desktop.png"), full_page=True)
            search = page.get_by_label("Search Furnace setup help")
            search.fill("install")
            search.press("Enter")
            expect(
                page.get_by_role("region", name="Setup help results").get_by_role(
                    "link", name="Set up Furnace", exact=False
                )
            ).to_be_visible()
            search.fill("no-such-guide-987654")
            search.press("Enter")
            expect(page.get_by_role("status")).to_contain_text("No matching guides")
            search.fill("")
            expect(page.get_by_role("region", name="Setup help results")).to_have_count(0)
            page.set_viewport_size({"width": 390, "height": 844})
            page.reload(wait_until="networkidle")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(screenshots / "public-home-mobile.png"), full_page=True)
            toggle = page.get_by_role("button", name="Toggle navigation")
            toggle.click()
            expect(toggle).to_have_attribute("aria-expanded", "true")
            page.get_by_role("navigation", name="Main navigation").get_by_role(
                "link", name="Get started", exact=True
            ).click()
            expect(
                page.get_by_role("heading", name="Your first workspace, one step at a time.")
            ).to_be_visible()
            expect(toggle).to_have_attribute("aria-expanded", "false")
            page.get_by_label("Linux", exact=True).check()
            for label in ("Git", "Python 3.12", "uv", "Internet access for the first installation"):
                page.get_by_label(label, exact=True).check()
            expect(page.get_by_text("Your checklist is complete.", exact=False)).to_be_visible()
            page.get_by_label("macOS", exact=True).check()
            expect(
                page.get_by_text("macOS onboarding has not been verified.", exact=False)
            ).to_be_visible()
            # Test browser-local success/denial paths without reading/writing the user's OS clipboard.
            page.evaluate("""() => {
              Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{
                writeText:async text => { window.copiedFurnaceCommands = text; }
              }});
            }""")
            page.get_by_role("button", name="Copy commands").click()
            expect(page.get_by_role("status")).to_contain_text("Commands copied")
            commands = page.evaluate("window.copiedFurnaceCommands")
            assert commands.startswith("git clone https://github.com/dilipna/Furnace4LLM.git\n")
            assert commands.endswith("uv run furnace studio")
            page.evaluate(
                "() => { navigator.clipboard.writeText = async () => { throw new Error('denied'); }; }"
            )
            page.get_by_role("button", name="Copy commands").click()
            expect(page.get_by_role("status")).to_contain_text("Copy is unavailable")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(screenshots / "setup-mobile.png"), full_page=True)
            for route, expected in [
                ("/pricing", "Start with the free workspace."),
                ("/research", "Same runbook."),
                ("/demo", "Everything on this page is a recording, not a live run."),
            ]:
                page.goto(site + route, wait_until="networkidle", timeout=120000)
                expect(page.get_by_text(expected, exact=False).first).to_be_visible()
            assert not errors, errors
            assert not writes, "Public setup/search unexpectedly sent POST requests"
            return {
                "engine": browser.version,
                "desktop_mobile": "passed",
                "help_search": "matched_unmatched_and_clear",
                "navigation": "passed",
                "prerequisites": "self_report_not_machine_verification",
                "clipboard": "browser_local_success_denial_stubs; OS_clipboard_not_tested",
                "public_post_requests": 0,
            }
        finally:
            browser.close()


def studio_journey(channel: str | None, screenshots: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="furnace-interface-") as directory:
        root = Path(directory)
        token = secrets.token_urlsafe(32)
        app = create_app(root / "workspace", token)

        def no_docker(*args, **kwargs):
            raise AssertionError("The metadata/connector journey must not contact Docker")

        app.state.runtime.manager._docker = no_docker
        app.state.runtime.manager.readiness = lambda: {
            "status": "unavailable",
            "reason": "test_no_docker",
        }
        app.state.managed.supervisor._docker = no_docker
        app.state.managed.supervisor.daemon = lambda: {
            "status": "unavailable",
            "gpu_runtime": False,
        }
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def api(path, method="GET", value=None):
            data = json.dumps(value).encode() if value is not None else None
            request = urllib.request.Request(  # noqa: S310 -- generated literal-loopback server only
                base + "/api/" + path,
                data=data,
                method=method,
                headers={"X-Furnace-Session": token, "Content-Type": "application/json"},
            )
            with opener.open(request, timeout=30) as response:
                content = response.read()
                return (
                    content
                    if response.headers.get_content_type() == "application/zip"
                    else json.loads(content)
                    if content
                    else None
                )

        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Disposable Studio did not start")
                time.sleep(0.05)
            model = root / "metadata-project"
            model.mkdir()
            (model / "config.json").write_text('{"model_type":"metadata_only"}')
            (model / "research.py").write_text("raise RuntimeError('must not execute')")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel=channel)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                server_errors = []
                page.on(
                    "response",
                    lambda response: (
                        server_errors.append(response.status) if response.status >= 500 else None
                    ),
                )
                try:
                    page.goto(base + "/#session=" + token)
                    expect(
                        page.get_by_role("heading", name="What would you like to work on?")
                    ).to_be_visible()
                    expect(page.locator("#add-form")).not_to_be_visible()
                    page.screenshot(
                        path=str(screenshots / "studio-welcome-desktop.png"), full_page=True
                    )
                    page.get_by_role("button", name="Add my model project", exact=True).click()
                    expect(page.locator('#add-form input[name="name"]')).to_be_focused()
                    page.locator('#add-form input[name="name"]').fill("Interface metadata project")
                    page.locator('#add-form input[name="path"]').fill(str(model))
                    page.locator('#add-form button[type="submit"]').click()
                    expect(page.locator("#project-title")).to_have_text(
                        "Interface metadata project"
                    )
                    saved_projects = api("projects")
                    assert isinstance(saved_projects, list) and len(saved_projects) == 1
                    project = saved_projects[0]
                    assert not project["assessment"]["execution_performed"]
                    page.locator("#new-project").click()
                    expect(page.locator('#add-form input[name="name"]')).to_be_focused()
                    page.locator("#hero-example").click()
                    expect(page.locator("#example-note")).to_be_visible()
                    saved_projects = api("projects")
                    assert isinstance(saved_projects, list)
                    guided = next(
                        item for item in saved_projects if item.get("origin") == "guided_example"
                    )
                    assert guided["evaluation"] is None
                    with page.expect_download() as exported:
                        page.locator("#download").click()
                    archive_path = exported.value.path()
                    assert archive_path is not None
                    with zipfile.ZipFile(archive_path) as archive:
                        assert archive.namelist()
                    # The second project must survive workspace/model navigation and
                    # reload. A missing explicit identity must not pick the first.
                    page.goto(base + "/?project=" + guided["id"] + "#session=" + token)
                    expect(page.locator("#project-title")).to_have_text(guided["name"])
                    expect(page).not_to_have_url(re.compile("#session"))
                    page.locator("#model-workspace-link").click()
                    expect(page.locator("#model-project")).to_have_value(guided["id"])
                    page.goto(base + "/model?project=" + guided["id"] + "#session=" + token)
                    expect(page.locator("#model-project")).to_have_value(guided["id"])
                    expect(page).not_to_have_url(re.compile("#session"))
                    page.reload(wait_until="networkidle")
                    expect(page.locator("#model-project")).to_have_value(guided["id"])
                    page.get_by_role("link", name="Back to workspace", exact=False).click()
                    expect(page.locator("#project-title")).to_have_text(guided["name"])
                    page.goto(base + "/model?project=deleted-project")
                    expect(page.locator("#model-notice")).to_contain_text("unavailable")
                    expect(page.locator("#model-project")).to_have_value("")
                    expect(page.locator("#model-workspace")).not_to_be_visible()
                    page.reload(wait_until="networkidle")
                    expect(page.locator("#model-project")).to_have_value("")
                    expect(page.locator("#model-workspace")).not_to_be_visible()
                    # Run the actual CLI kit -> browser parser -> saved API cases ->
                    # UI kit export round trip, not a hand-authored imitation.
                    cli_kit = root / "cli-kit"
                    export_starter(model, cli_kit)
                    page.goto(base + "/?project=" + project["id"])
                    page.locator('[data-view="evaluations"]').click()
                    page.locator("#case-import-file").set_input_files(
                        cli_kit / "evaluation-cases.example.jsonl"
                    )
                    expect(page.locator("#case-import-status")).to_contain_text(
                        "cases ready for review"
                    )
                    page.locator("#case-import-save").click()
                    expect(page.locator("#notice")).to_contain_text("saved")
                    imported = api(f"projects/{project['id']}")
                    assert imported["cases"][0]["scoring"]["number"] == 180
                    assert imported["cases"][0]["status"] == "not_run"
                    assert imported["model_endpoint"]["evaluation"] is None
                    page.locator('[data-view="overview"]').click()
                    with page.expect_download() as roundtrip:
                        page.locator("#download").click()
                    with zipfile.ZipFile(roundtrip.value.path()) as archive:
                        exported_case = json.loads(archive.read("evaluation-cases.example.jsonl"))
                        assert exported_case == imported["cases"][0]
                    api(
                        f"projects/{project['id']}/contract",
                        "PUT",
                        {"notes": "Reviewed test interface"},
                    )
                    api(
                        f"projects/{project['id']}/plan",
                        "PUT",
                        {
                            "compute": "customer",
                            "memory_gb": 2,
                            "timeout_seconds": 30,
                            "log_retention_days": 7,
                        },
                    )
                    page.reload(wait_until="networkidle")
                    expect(page.locator("#next-action")).to_have_text("Open model infrastructure →")
                    page.locator("#next-action").click()
                    expect(page.locator("#model-project")).to_have_value(project["id"])
                    assert api(f"projects/{project['id']}")["evaluation"] is None
                    page.goto(base + "/?project=" + guided["id"])
                    expect(page.locator("#capabilities")).not_to_be_visible()
                    page.locator(".assessment-details > summary").click()
                    expect(page.locator("#capabilities > *")).to_have_count(6)
                    expect(page.locator("#capabilities")).to_be_visible()
                    page.locator(".assessment-details > summary").click()
                    page.screenshot(
                        path=str(screenshots / "studio-workspace-desktop.png"), full_page=True
                    )
                    print("Studio metadata and guided example saved", flush=True)
                    assert not server_errors, server_errors
                    api(f"projects/{project['id']}", "DELETE")
                    assert (model / "research.py").is_file()
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.goto(base + "/#session=" + token)
                    expect(page.locator("#project-title")).to_be_visible()
                    # The session link rewrites the URL after load; measure once it settles.
                    page.wait_for_load_state("networkidle")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.screenshot(
                        path=str(screenshots / "studio-workspace-mobile.png"), full_page=True
                    )
                    page.goto(base + "/model#session=" + token)
                    page.locator("#managed-model").select_option("qwen2.5-0.5b-instruct-q8_0")
                    expect(page.get_by_label("CPU threads", exact=True)).not_to_be_visible()
                    page.locator("#managed-advanced > summary").click()
                    page.get_by_label("CPU threads", exact=True).fill("2")
                    page.locator("#managed-advanced > summary").click()
                    page.get_by_role("button", name="Save model selection", exact=True).click()
                    expect(page.locator("#managed-status")).to_contain_text("Selection saved")
                    saved = api(f"projects/{guided['id']}/managed")
                    assert isinstance(saved, dict)
                    assert saved["selection"]["threads"] == 2
                    assert saved["status"] == "configured"
                    assert not (root / "workspace" / "artifacts").exists()
                    assert not page.locator("#managed-consent").is_checked()
                    expect(page.locator("#managed-prepare")).to_be_disabled()
                finally:
                    browser.close()
            result = verify_connector(
                base,
                token,
                api,
                guided["id"],
                root,
                browser=True,
                screenshots=screenshots,
                browser_channel=channel,
            )
            return {
                "welcome_project_disclosure": "passed",
                "metadata_project_and_guided_example": "actual_API_persistence_no_execution",
                "docker_calls": 0,
                "starter_kit_ui_download": "actual_zip_downloaded_and_opened",
                "cli_kit_cases": "exported_parsed_saved_and_reexported_through_UI; not_run",
                "project_handoff": "second_project_preserved_across_navigation_and_reload; missing_refused",
                "researcher_next_action": "real_model_workspace_without_fixture_execution; setup_persisted_via_API",
                "managed_selection": "persisted_without_consent_download_or_execution; advanced_values_preserved",
                "hardware_catalog": "mocked_unavailable; no_machine_compatibility_claim",
                "connector": result,
            }
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            assert not thread.is_alive(), "Disposable Studio did not shut down"
            gc.collect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-url", default="http://127.0.0.1:3008")
    parser.add_argument("--browser-channel", default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    faulthandler.dump_traceback_later(120, repeat=True)
    url = urlsplit(args.site_url)
    if url.scheme != "http" or url.hostname != "127.0.0.1":
        raise SystemExit("Use a literal loopback test site")
    args.screenshots.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if git is None:
        raise SystemExit("Git is required to record the tested source")
    report = {
        "source_commit": subprocess.check_output([git, "rev-parse", "HEAD"], text=True).strip(),  # noqa: S603 -- resolved Git, fixed read-only arguments
        "source_dirty": bool(
            subprocess.check_output([git, "status", "--porcelain"], text=True).strip()  # noqa: S603 -- resolved Git, fixed read-only arguments
        ),
        "public": public_journey(args.site_url.rstrip("/"), args.browser_channel, args.screenshots),
        "studio": studio_journey(args.browser_channel, args.screenshots),
        "model_inference": False,
        "human_comprehension": "not_tested",
        "native_file_picker": "not_tested",
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    faulthandler.cancel_dump_traceback_later()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
