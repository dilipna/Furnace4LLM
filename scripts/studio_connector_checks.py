"""Installed connector checks. HTTP test servers return authored text, never inference."""

from __future__ import annotations

import contextlib
import io
import json
import threading
import urllib.error
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ANSWER = "HTTP TRANSPORT TEST — NO MODEL"
MODEL = "http-test-not-a-model"


class Probe:
    def __init__(self):
        self.requests: list[tuple[str, dict | None]] = []
        self.mode = "normal"

    def __enter__(self):
        probe = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def reply(self, value, status=200):
                raw = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    self.wfile.write(raw)

            def do_GET(self):
                probe.requests.append((self.path, None))
                self.reply({"data": [{"id": MODEL}]})

            def do_POST(self):
                value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                probe.requests.append((self.path, value))
                if probe.mode == "error":
                    self.reply({"error": "PRIVATE UPSTREAM TEXT"}, 500)
                    return
                self.reply(
                    {
                        "model": MODEL,
                        "choices": [
                            {
                                "message": {
                                    "content": "\ud800" if probe.mode == "surrogate" else ANSWER
                                },
                                "finish_reason": "stop",
                            }
                        ],
                    }
                )

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.config = {
            "base_url": f"http://127.0.0.1:{self.server.server_port}/v1",
            "model_id": MODEL,
            "declared_revision": "test-server-only",
            "timeout_seconds": 2,
            "max_tokens": 16,
        }
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


def verify_connector(
    base, session, api, pid, root, *, browser=False, screenshots=None, browser_channel=None
):
    with Probe() as probe:
        path = f"projects/{pid}/model"
        api(
            f"projects/{pid}/cases",
            "PUT",
            {
                "cases": [
                    {
                        "name": "Exact transport text",
                        "input": "test",
                        "expected_behavior": "Exact authored HTTP test response",
                        "expected_output": ANSWER,
                    },
                    {
                        "name": "Needs human scoring",
                        "input": "test",
                        "expected_behavior": "Descriptive expectation is unscored",
                    },
                ]
            },
        )
        api(path + "/connection", "PUT", probe.config)
        assert probe.requests == []
        try:
            api(path + "/connect", "POST", {"consent": False})
            raise AssertionError("Missing consent accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 409
        assert probe.requests == []
        api(path + "/connect", "POST", {"consent": True})
        assert probe.requests == [("/v1/models", None)]
        result = api(path + "/predict", "POST", {"input": "test"})
        assert result["output"] == ANSWER
        body = probe.requests[-1][1]
        assert body is not None and body["messages"] == [{"role": "user", "content": "test"}]
        probe.mode = "surrogate"
        before_invalid = len(probe.requests)
        try:
            api(path + "/predict", "POST", {"input": "test"})
            raise AssertionError("Invalid upstream Unicode accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 409
            assert json.loads(error.read())["detail"] == "endpoint_invalid_or_mismatched_completion"
        assert len(probe.requests) == before_invalid + 1
        assert api(path)["model_endpoint"]["state"]["status"] == "failed"
        probe.mode = "normal"
        api(path + "/connect", "POST", {"consent": True})
        probe.mode = "error"
        failed = api(path + "/evaluate", "POST")["model_endpoint"]
        assert failed["state"]["status"] == "failed"
        assert failed["evaluation"]["status"] == "interrupted"
        before = len(probe.requests)
        try:
            api(path + "/evaluate", "POST")
            raise AssertionError("Failed connection retried without reconnect")
        except urllib.error.HTTPError as error:
            assert error.code == 409
        assert len(probe.requests) == before
        probe.mode = "normal"
        api(path + "/connect", "POST", {"consent": True})
        completed = api(path + "/evaluate", "POST")
        assert len(probe.requests) == before + 3
        assert [r["status"] for r in completed["model_endpoint"]["evaluation"]["results"]] == [
            "exact_pass",
            "unscored",
        ]
        assert completed["evaluation"] is None
        assert [run["status"] for run in completed["model_endpoint"]["history"]] == [
            "interrupted",
            "completed",
        ]
        assert completed["model_endpoint"]["history"][0]["run_id"] == failed["evaluation"]["run_id"]
        report = {
            "http_test_server_only": True,
            "installed_api_checks": "passed",
            "malformed_unicode_refused": "passed",
        }
        if browser:
            report["browser"] = verify_browser(
                base,
                session,
                api,
                pid,
                root,
                probe,
                screenshots=screenshots,
                browser_channel=browser_channel,
            )
        saved = api(path)
        with zipfile.ZipFile(io.BytesIO(api(f"projects/{pid}/kit", "POST"))) as archive:
            endpoint = json.loads(archive.read("workspace-plan.json"))["model_endpoint"]
            assert endpoint["evaluation"]["project_id"] == pid
            assert (
                endpoint["configuration_sha256"] == saved["model_endpoint"]["configuration_sha256"]
            )
            assert endpoint["verification"] == "current_endpoint_observation"
            assert endpoint["history"] == saved["model_endpoint"]["history"]
        report["saved_run_id"] = saved["model_endpoint"]["evaluation"]["run_id"]
        report["saved_history_ids"] = [run["run_id"] for run in saved["model_endpoint"]["history"]]
        report["actual_http_requests"] = len(probe.requests)
        return report


def verify_case_import(page, base, session, api, pid, other_id, probe, screenshots):
    from playwright.sync_api import expect

    page.goto(base + "/#session=" + session)
    page.locator('[data-view="evaluations"]').click()
    picker = page.get_by_label("Case suite JSONL file")
    status = page.locator("#case-import-status")
    preview = page.locator("#case-import-preview")
    replace = page.get_by_role("button", name="Replace saved cases with preview")
    before = api(f"projects/{pid}/model")
    calls = len(probe.requests)
    picker.set_input_files(
        {"name": "invalid.jsonl", "mimeType": "application/x-ndjson", "buffer": b"{PRIVATE INVALID"}
    )
    expect(status).to_contain_text("Line 1: invalid JSON")
    expect(status).not_to_contain_text("PRIVATE")
    expect(replace).to_be_disabled()
    assert api(f"projects/{pid}/model")["cases"] == before["cases"]
    assert api(f"projects/{pid}/model")["revision"] == before["revision"]
    cases = [
        {
            "name": "Imported transport exact",
            "input": "test",
            "expected_behavior": "Exact authored HTTP test response",
            "expected_output": ANSWER,
            "status": "framework_pass",
        },
        {
            "name": "Imported descriptive case",
            "input": "test",
            "expected_behavior": "Needs human scoring",
            "recorded_status": "framework_pass",
        },
    ]
    content = "\n".join(json.dumps(item) for item in cases).encode()
    # Delay an actual file read, then change project before its preview arrives.
    page.evaluate("""() => {
      const read = File.prototype.arrayBuffer;
      File.prototype.arrayBuffer = async function() {
        const bytes = await read.call(this);
        if (this.name === 'delayed.jsonl') await new Promise(resolve => { window.releaseCaseImportRead = resolve; });
        return bytes;
      };
    }""")
    picker.set_input_files(
        {"name": "delayed.jsonl", "mimeType": "application/x-ndjson", "buffer": content}
    )
    page.wait_for_function("typeof window.releaseCaseImportRead === 'function'")
    page.locator(f'[data-project="{other_id}"]').click()
    page.locator('[data-view="evaluations"]').click()
    page.evaluate("releaseCaseImportRead()")
    expect(preview.locator("li")).to_have_count(0)
    expect(replace).to_be_disabled()
    page.locator(f'[data-project="{pid}"]').click()
    page.locator('[data-view="evaluations"]').click()
    expect(preview.locator("li")).to_have_count(2)
    expect(status).to_contain_text("2 imported result labels discarded")
    assert api(f"projects/{pid}/model")["cases"] == before["cases"]
    assert api(f"projects/{pid}/model")["revision"] == before["revision"]
    # A different window edits after preview; the backend must reject the stale save.
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
        page.evaluate("scrollTo(0, 0)")
        page.screenshot(path=str(screenshots / "case-import-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("scrollTo(0, 0)")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(screenshots / "case-import-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
    api(
        f"projects/{pid}/contract",
        "PUT",
        {"architecture": "Preserved metadata only", "notes": "Edited after preview"},
    )
    replace.click()
    expect(page.locator("#notice")).to_contain_text("changed after preview")
    assert api(f"projects/{pid}/model")["cases"] == before["cases"]
    page.locator('[data-view="infrastructure"]').click()
    page.locator("#refresh-runtime").click()
    expect(page.locator("#refresh-runtime")).to_be_enabled()
    page.locator('[data-view="evaluations"]').click()
    expect(status).to_contain_text("Project changed after preview")
    expect(replace).to_be_disabled()
    picker.set_input_files(
        {"name": "valid.jsonl", "mimeType": "application/x-ndjson", "buffer": content}
    )
    expect(replace).to_be_enabled()
    replace.click()
    expect(page.locator("#notice")).to_contain_text("Imported cases saved")
    saved = api(f"projects/{pid}/model")
    assert [item["name"] for item in saved["cases"]] == [item["name"] for item in cases]
    assert [item["status"] for item in saved["cases"]] == ["not_run", "not_run"]
    assert saved["evaluation"] is None
    assert api(f"projects/{other_id}/model")["cases"] == []
    assert len(probe.requests) == calls
    # Starter-kit JSONL includes saved status metadata, and round-trips safely.
    with zipfile.ZipFile(io.BytesIO(api(f"projects/{pid}/kit", "POST"))) as archive:
        exported = archive.read("evaluation-cases.example.jsonl")
    picker.set_input_files(
        {"name": "from-kit.jsonl", "mimeType": "application/x-ndjson", "buffer": exported}
    )
    expect(preview.locator("li")).to_have_count(2)
    expect(status).to_contain_text("2 imported result labels discarded")
    page.get_by_role("button", name="Discard import preview").click()
    expect(preview.locator("li")).to_have_count(0)


def verify_browser(
    base, session, api, pid, root, probe, *, screenshots: Path | None, browser_channel=None
):
    from playwright.sync_api import expect, sync_playwright

    def reveal_panel(page, selector):
        if page.locator(selector).get_attribute("open") is None:
            page.locator(selector + " > summary").click()

    other = root / "other-project"
    other.mkdir()
    second = api("projects", "POST", {"name": "Other HTTP test project", "path": str(other)})
    other_id = second["id"]
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=browser_channel)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            verify_case_import(page, base, session, api, pid, other_id, probe, screenshots)
            page.goto(base + "/model#session=" + session)
            selector = page.get_by_label("Workspace project")
            expect(selector).to_have_value(pid)
            expect(
                page.get_by_role("heading", name="Or describe a server you operate")
            ).to_be_visible()
            # The Furnace-operated panel is checked separately; collapsed, only its summary is
            # in the tab order, so this walk covers the connection controls as before.
            page.locator("#managed-settings").evaluate("details => { details.open = false; }")
            assert "session=" not in page.url
            page.keyboard.press("Tab")
            expect(page.get_by_role("link", name="Skip to model connection")).to_be_focused()
            page.keyboard.press("Enter")
            expect(page.locator("#model-main")).to_be_focused()
            for control in [
                selector,
                page.get_by_role("button", name="Refresh saved state"),
                page.locator("#managed-settings > summary"),
                page.locator("#connection-settings > summary"),
                page.get_by_label("Local API base URL"),
                page.get_by_label("Exact advertised model ID"),
                page.get_by_label("Declared code/checkpoint or server revision"),
                page.get_by_label("Request timeout, seconds", exact=True),
                page.get_by_label("Maximum generated tokens", exact=True),
                page.get_by_label("Evaluation budget, seconds", exact=True),
                page.get_by_role("button", name="Save connection settings"),
                page.locator("#model-consent"),
            ]:
                page.keyboard.press("Tab")
                expect(control).to_be_focused()
            page.keyboard.press("Space")
            expect(page.locator("#model-consent")).to_be_checked()
            page.keyboard.press("Space")

            # Connection settings and prompt drafts must remain scoped to their project.
            revision = page.get_by_label("Declared code/checkpoint or server revision")
            revision.fill("unsaved-owner-draft")
            prompt = page.get_by_label("Sanitized text input")
            prompt.fill("project-one-draft")
            selector.select_option(other_id)
            expect(prompt).to_have_value("")
            expect(revision).to_have_value("")
            selector.select_option(pid)
            expect(prompt).to_have_value("project-one-draft")
            expect(revision).to_have_value("unsaved-owner-draft")
            page.get_by_role("button", name="Refresh saved state").click()
            expect(revision).to_have_value("unsaved-owner-draft")
            revision.fill(probe.config["declared_revision"])
            page.get_by_role("button", name="Save connection settings").click()
            expect(page.locator("#connection-draft")).to_contain_text("Saved settings")
            page.get_by_role("button", name="Check and connect").click()
            expect(page.get_by_role("status").first).to_contain_text("Confirm that you operate")
            consent = page.locator("#model-consent")
            consent.check()
            page.get_by_role("button", name="Check and connect").click()
            expect(page.locator("#model-state")).to_contain_text("connected")
            page.get_by_role("button", name="Send to local server").click()
            expect(page.locator("#model-output")).to_contain_text(ANSWER)
            page.locator("#connection-settings > summary").click()
            expect(page.get_by_label("Local API base URL")).not_to_be_visible()
            expect(page.get_by_role("button", name="Send to local server")).to_be_enabled()
            if screenshots:
                page.screenshot(path=str(screenshots / "connector-message.png"), full_page=True)
            reveal_panel(page, "#endpoint-checks")
            page.get_by_role("button", name="Run endpoint cases").click()
            expect(page.locator("#model-results")).to_contain_text("exact_pass")
            expect(page.locator("#model-results")).to_contain_text("unscored")
            expect(page.locator("#model-run")).to_contain_text("completed")
            reveal_panel(page, "#endpoint-history")
            history = page.locator("#model-history")
            failed_attempt = history.locator("details").filter(has_text="interrupted")
            expect(failed_attempt).to_have_count(1)
            expect(page.get_by_role("button", name="Send to local server")).to_be_enabled()
            before_inspection = len(probe.requests)
            failed_attempt.locator("summary").focus()
            page.keyboard.press("Enter")
            expect(failed_attempt).to_have_attribute("open", "")
            expect(failed_attempt).to_contain_text("error: 1")
            expect(failed_attempt).to_contain_text("not_run: 1")
            assert len(probe.requests) == before_inspection
            page.get_by_role("button", name="Send to local server").click()
            expect(page.get_by_role("button", name="Send to local server")).to_be_enabled()
            expect(failed_attempt).to_have_attribute("open", "")
            with page.expect_download() as download:
                page.get_by_role("button", name="Export kit with both evidence types").click()
            with zipfile.ZipFile(download.value.path()) as archive:
                exported = json.loads(archive.read("workspace-plan.json"))["model_endpoint"]
                assert exported["evaluation"]["project_id"] == pid
                assert exported["history"][0]["status"] == "interrupted"

            # Deliver a real response late, after another project becomes selected.
            held = []

            def delay_predict(route):
                held.append((route, route.fetch()))

            prediction = "**/api/projects/" + pid + "/model/predict"
            page.route(prediction, delay_predict)
            page.get_by_role("button", name="Send to local server").click()
            expect(page.get_by_role("button", name="Send to local server")).to_be_disabled()
            page.wait_for_function(
                "document.querySelector('#model-notice').textContent.includes('Working')"
            )
            # Pump browser events until the intercepted request has reached the actual app.
            for _ in range(100):
                if held:
                    break
                page.wait_for_timeout(20)
            assert held
            selector.select_option(other_id)
            expect(history.locator("details")).to_have_count(0)
            held[0][0].fulfill(response=held[0][1])
            expect(selector).to_have_value(other_id)
            expect(page.locator("#model-notice")).to_contain_text("Request completed")
            expect(page.locator("#model-output")).not_to_contain_text(ANSWER)
            page.unroute(prediction, delay_predict)
            selector.select_option(pid)
            expect(page.get_by_role("button", name="Send to local server")).to_be_enabled()

            # A configuration change must fence even an already-returned completion.
            held.clear()
            page.route(prediction, delay_predict)
            page.get_by_role("button", name="Send to local server").click()
            for _ in range(100):
                if held:
                    break
                page.wait_for_timeout(20)
            assert held
            api(
                f"projects/{pid}/contract",
                "PUT",
                {"architecture": "Preserved metadata only", "notes": "Changed during response"},
            )
            page.get_by_role("button", name="Refresh saved state").click()
            expect(page.locator("#model-state")).to_contain_text("unconfirmed")
            held[0][0].fulfill(response=held[0][1])
            expect(page.locator("#model-notice")).to_contain_text("Request completed")
            expect(page.locator("#model-output")).not_to_contain_text(ANSWER)
            expect(page.locator("#model-run")).not_to_contain_text("completed")
            expect(
                history.locator("summary").filter(has_text="Current saved configuration")
            ).to_have_count(0)
            expect(
                history.locator("summary").filter(has_text="Earlier or unbound configuration")
            ).to_have_count(3)
            page.unroute(prediction, delay_predict)

            # Two refreshes resolve out of order, with a deletion between snapshots.
            snapshots = []

            def hold_first_snapshot(route):
                if not snapshots:
                    snapshots.append((route, route.fetch()))
                else:
                    route.continue_()

            page.route("**/api/projects", hold_first_snapshot)
            page.get_by_role("button", name="Refresh saved state").click()
            for _ in range(100):
                if snapshots:
                    break
                page.wait_for_timeout(20)
            assert snapshots
            api(f"projects/{other_id}", "DELETE")
            page.get_by_role("button", name="Refresh saved state").click()
            expect(selector.locator("option")).to_have_count(1)
            print("Browser refresh reproduction: newest snapshot has one project", flush=True)
            with page.expect_event(
                "requestfinished", predicate=lambda request: request == snapshots[0][0].request
            ):
                snapshots[0][0].fulfill(response=snapshots[0][1])
            # Let the completed fetch's promise handlers render before inspecting absence.
            page.evaluate("new Promise(resolve => requestAnimationFrame(resolve))")
            print(
                "Browser refresh reproduction: after old response, project count =",
                selector.locator("option").count(),
                flush=True,
            )
            expect(selector.locator("option")).to_have_count(1)
            page.unroute("**/api/projects", hold_first_snapshot)

            snapshots.clear()
            page.route("**/api/projects", hold_first_snapshot)
            page.get_by_role("button", name="Refresh saved state").click()
            for _ in range(100):
                if snapshots:
                    break
                page.wait_for_timeout(20)
            assert snapshots
            page.get_by_role("button", name="Refresh saved state").click()
            expect(page.locator("#model-state")).not_to_contain_text("Reconfirming")
            with page.expect_event(
                "requestfinished", predicate=lambda request: request == snapshots[0][0].request
            ):
                snapshots[0][0].fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"detail":"old refresh failed"}',
                )
            page.evaluate("new Promise(resolve => requestAnimationFrame(resolve))")
            expect(page.locator("#model-notice")).not_to_contain_text("old refresh failed")
            page.unroute("**/api/projects", hold_first_snapshot)

            # Reload/navigation only read saved metadata; neither repeats endpoint calls.
            count = len(probe.requests)
            page.reload()
            expect(selector).to_have_value(pid)
            expect(revision).to_have_value(probe.config["declared_revision"])
            expect(consent).not_to_be_checked()
            expect(prompt).to_have_value("")
            page.get_by_role("link", name="Model validation requirements").click()
            page.go_back()
            expect(selector).to_have_value(pid)
            assert len(probe.requests) == count
            consent.check()
            page.get_by_role("button", name="Check and connect").click()
            reveal_panel(page, "#endpoint-checks")
            expect(page.get_by_role("button", name="Run endpoint cases")).to_be_enabled()
            page.get_by_role("button", name="Run endpoint cases").click()
            expect(page.locator("#model-run")).to_contain_text("completed")
            # Exercise the persisted-pageshow handler without claiming a BFCache hit.
            page.route("**/api/projects", lambda route: route.abort())
            page.evaluate("dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
            expect(page.locator("#model-notice")).to_contain_text("Saved state not confirmed")
            expect(page.locator("#model-run")).not_to_contain_text("completed")
            expect(history.locator("details")).to_have_count(0)
            expect(page.get_by_role("button", name="Send to local server")).to_be_disabled()
            expect(consent).not_to_be_checked()
            expect(page.get_by_role("button", name="Refresh saved state")).to_be_enabled()
            page.unroute("**/api/projects")
            page.get_by_role("button", name="Refresh saved state").click()
            expect(page.locator("#model-run")).to_contain_text("completed")
            expect(page.locator("#model-notice")).not_to_contain_text("Saved state not confirmed")
            page.evaluate("scrollTo(0, 0)")
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "connector-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("scrollTo(0, 0)")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            if screenshots:
                page.screenshot(path=str(screenshots / "connector-mobile.png"), full_page=True)
            assert errors == [], errors
            return {
                "engine": browser.version,
                "checks": "passed",
                "human_comprehension": "not_tested",
                "bfcache_use": "not_asserted",
                "persisted_pageshow_failure_recovery": "synthetic_event_passed",
                "attempt_history": "failed_attempt_inspected_without_execution; retained_after_retry_and_configuration_edit; project_scoped; exported",
                "case_import": "invalid_and_delayed_reads_safe; stale_replace_refused; explicit_replace_reset_statuses; kit_jsonl_round_trip",
            }
        except Exception:
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "connector-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
