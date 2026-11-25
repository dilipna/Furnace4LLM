"""Exercise installed code with no developer tools on PATH and real browser/API calls."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    parser.add_argument("--browser-executable", type=Path)
    args = parser.parse_args()
    args.app = args.app.resolve()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="furnace-installed-smoke-"))
    build = json.loads((args.app / "build.json").read_text())
    record = {
        "schema": "furnace-installed-smoke-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "build": build,
        "checks": {},
        "model_inference": False,
        "clean_profile": False,
    }
    checks = record["checks"]
    completed = False
    env = {
        **os.environ,
        "PATH": os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "System32"),
        "PYTHONHOME": "invalid-test-value",
        "PYTHONPATH": "invalid-test-value",
    }
    child = subprocess.Popen(  # noqa: S603 -- installed interpreter, test-owned probe and workspace
        [
            str(args.app / "runtime/python.exe"),
            "-I",
            str(ROOT / "scripts/installed_probe.py"),
            str(args.app),
            str(workspace),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        assert child.stdout is not None
        ready = json.loads(child.stdout.readline())
        assert ready["url"].startswith("http://127.0.0.1:")
        checks["installed_code_with_no_python_uv_git_on_path"] = True
        record["installed_module"] = ready["installed_module"]
        headers = {"x-furnace-session": ready["token"]}

        def api(path: str):
            return httpx.get(
                ready["url"] + "/api/" + path, headers=headers, timeout=30, trust_env=False
            ).json()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=str(args.browser_executable) if args.browser_executable else None
            )
            page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "console",
                lambda message: errors.append(message.text) if message.type == "error" else None,
            )
            page.goto(ready["url"] + "/#session=" + ready["token"])
            expect(page.get_by_text("INFRASTRUCTURE FOR YOUR MODEL", exact=True)).to_be_visible()
            checks["researcher_home_opened"] = True
            expect(
                page.get_by_role("heading", name="What would you like to work on?")
            ).to_be_visible()
            try:
                expect(page.locator("#first-run")).to_be_visible(timeout=30000)
            except Exception:
                record["browser_errors"] = [
                    message.replace(ready["token"], "<redacted>") for message in errors
                ]
                page.screenshot(path=str(args.screenshots / "failed-first-run.png"), full_page=True)
                record["diagnostic_system_response"] = httpx.get(
                    ready["url"] + "/api/system", headers=headers, timeout=30, trust_env=False
                ).status_code
                raise
            checks["opened_studio_in_browser"] = True
            system = api("system")
            record["preflight"] = system["runtime"]
            checks["preflight_read_only"] = system["workspace"] == "available"
            page.screenshot(path=str(args.screenshots / "studio-home.png"), full_page=True)
            page.get_by_role("button", name="Open guided example", exact=False).click()
            expect(page.locator("#count")).to_have_text("1 / 2")
            projects = api("projects")
            checks["guided_example_saved"] = len(projects) == 1 and len(projects[0]["cases"]) == 2
            page.screenshot(path=str(args.screenshots / "studio-example.png"), full_page=True)
            with page.expect_download() as exported:
                page.locator("#download").click()
            archive_path = exported.value.path()
            assert archive_path is not None
            with zipfile.ZipFile(archive_path) as archive:
                checks["kit_export"] = bool(archive.namelist())
            checks["kit_export_through_ui"] = True
            checks["no_browser_errors"] = not errors
            record["browser_errors"] = [
                message.replace(ready["token"], "<redacted>") for message in errors
            ]
            browser.close()
        assert all(checks.values()), record
        completed = True
    finally:
        if child.stdin:
            with contextlib.suppress(OSError):
                child.stdin.write("quit\n")
                child.stdin.flush()
        stdout, stderr = child.communicate(timeout=60)
        checks["quit_and_lease_released"] = (
            child.returncode == 0 and '"lease_released": true' in stdout
        )
        if child.returncode:
            raise RuntimeError("Installed Studio probe failed: " + stderr[-1000:])
        record["completed"] = completed
        record["result"] = "passed" if completed and all(checks.values()) else "failed"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    assert record["result"] == "passed"
    print(args.out)


if __name__ == "__main__":
    main()
