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
                        "choices": [{"message": {"content": ANSWER}, "finish_reason": "stop"}],
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


def verify_connector(base, session, api, pid, root, *, browser=False, screenshots=None):
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
        assert probe.requests[-1][1]["messages"] == [{"role": "user", "content": "test"}]
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
        report = {"http_test_server_only": True, "installed_api_checks": "passed"}
        if browser:
            report["browser"] = verify_browser(
                base, session, api, pid, root, probe, screenshots=screenshots
            )
        saved = api(path)
        with zipfile.ZipFile(io.BytesIO(api(f"projects/{pid}/kit", "POST"))) as archive:
            endpoint = json.loads(archive.read("workspace-plan.json"))["model_endpoint"]
            assert endpoint["evaluation"]["project_id"] == pid
            assert (
                endpoint["configuration_sha256"] == saved["model_endpoint"]["configuration_sha256"]
            )
            assert endpoint["verification"] == "current_endpoint_observation"
        report["saved_run_id"] = saved["model_endpoint"]["evaluation"]["run_id"]
        report["actual_http_requests"] = len(probe.requests)
        return report


def verify_browser(base, session, api, pid, root, probe, *, screenshots: Path | None):
    from playwright.sync_api import expect, sync_playwright

    other = root / "other-project"
    other.mkdir()
    second = api("projects", "POST", {"name": "Other HTTP test project", "path": str(other)})
    other_id = second["id"]
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(base + "/model#session=" + session)
            selector = page.get_by_label("Workspace project")
            expect(selector).to_have_value(pid)
            expect(page.get_by_role("heading", name="2. Describe your server")).to_be_visible()
            assert "session=" not in page.url
            page.keyboard.press("Tab")
            expect(page.get_by_role("link", name="Skip to model connection")).to_be_focused()
            page.keyboard.press("Enter")
            expect(page.locator("#model-main")).to_be_focused()

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
            page.get_by_role("button", name="Run endpoint cases").click()
            expect(page.locator("#model-results")).to_contain_text("exact_pass")
            expect(page.locator("#model-results")).to_contain_text("unscored")
            expect(page.locator("#model-run")).to_contain_text("completed")
            with page.expect_download() as download:
                page.get_by_role("button", name="Export kit with both evidence types").click()
            with zipfile.ZipFile(download.value.path()) as archive:
                exported = json.loads(archive.read("workspace-plan.json"))["model_endpoint"]
                assert exported["evaluation"]["project_id"] == pid

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
            snapshots[0][0].fulfill(response=snapshots[0][1])
            # Wait for the older fetch's JS continuation, not just the newest response.
            page.wait_for_timeout(200)
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
            snapshots[0][0].fulfill(
                status=503, content_type="application/json", body='{"detail":"old refresh failed"}'
            )
            page.wait_for_timeout(200)
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
            expect(page.get_by_role("button", name="Run endpoint cases")).to_be_enabled()
            page.get_by_role("button", name="Run endpoint cases").click()
            expect(page.locator("#model-run")).to_contain_text("completed")
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "connector-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            if screenshots:
                page.screenshot(path=str(screenshots / "connector-mobile.png"), full_page=True)
            assert errors == [], errors
            return {
                "engine": browser.version,
                "checks": "passed",
                "human_comprehension": "not_tested",
                "bfcache_use": "not_asserted",
            }
        except Exception:
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "connector-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
