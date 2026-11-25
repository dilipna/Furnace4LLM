"""Record a real installed Qwen UI journey locally. No editing, publication or fabricated steps."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("dist/installed-demo"))
    parser.add_argument("--browser-executable", type=Path)
    args = parser.parse_args()
    args.app = args.app.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="furnace-recording-"))
    artifacts = Path.home() / ".furnace/artifacts"
    record = {
        "schema": "furnace-installed-recording-v1",
        "build": json.loads((args.app / "build.json").read_text()),
        "cache": "Shared verified-weights store; preparation still explicitly invoked",
        "editing": "Uncut browser recording; installer and app-window are separate still captures",
        "events": [],
        "result": "failed",
    }
    record["workspace"] = str(workspace)
    child = subprocess.Popen(  # noqa: S603 -- installed runtime and owned probe
        [
            str(args.app / "runtime/python.exe"),
            "-I",
            str(ROOT / "scripts/installed_probe.py"),
            str(args.app),
            str(workspace),
            str(artifacts),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout
        ready = json.loads(child.stdout.readline())
        assert ready["url"].startswith("http://127.0.0.1:")
        with (
            httpx.Client(
                base_url=ready["url"] + "/api/",
                headers={"x-furnace-session": ready["token"]},
                timeout=30,
                trust_env=False,
            ) as client,
            sync_playwright() as p,
        ):
            browser = p.chromium.launch(
                executable_path=str(args.browser_executable) if args.browser_executable else None
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                record_video_dir=str(args.out / "raw"),
                record_video_size={"width": 1280, "height": 900},
            )
            began = time.monotonic()
            page = context.new_page()

            def event(name: str, text: str) -> None:
                page.screenshot(path=str(args.out / (name + ".png")), full_page=True)
                record["events"].append(
                    {"stage": name, "seconds": round(time.monotonic() - began, 2), "caption": text}
                )
                (args.out / "progress.json").write_text(
                    json.dumps(record, indent=2) + "\n", encoding="utf-8"
                )
                print("Recorded stage: " + name, flush=True)
                page.wait_for_timeout(2000)

            def wait_state(path: str, predicate, timeout: int = 180):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    data = client.get(path).json()
                    if predicate(data):
                        return data
                    page.wait_for_timeout(250)
                raise RuntimeError("Timed out waiting for actual state: " + path)

            page.goto(ready["url"] + "/#session=" + ready["token"])
            page.get_by_role("button", name="Open guided example", exact=False).click()
            expect(page.locator("#count")).to_have_text("1 / 2")
            pid = client.get("projects").json()[0]["id"]
            event(
                "open",
                "Installed Furnace opened locally. The guided example is metadata, not an LLM.",
            )
            page.locator('header a[href="/model"]').click()
            page.locator("#managed-model").select_option(
                "qwen2.5-0.5b-instruct-q8_0", timeout=120000
            )
            with page.expect_response(
                lambda r: r.url.endswith("/managed") and r.request.method == "PUT"
            ) as saved:
                page.locator("#managed-save").click()
            assert saved.value.status == 200
            page.locator("#managed-consent").check()
            event(
                "selection",
                "Pinned Qwen CPU recipe selected. Downloads and execution require explicit consent.",
            )
            page.locator("#managed-prepare").click()
            prepared = wait_state(
                f"projects/{pid}/managed", lambda v: v["status"] in {"prepared", "failed"}, 900
            )
            record["prepare"] = {"status": prepared["status"], "reason": prepared.get("reason")}
            assert prepared["status"] == "prepared", prepared.get("reason")
            event(
                "prepared",
                "Preparation completed against cached assets; weights were verified. This is not model inference.",
            )
            with page.expect_response(lambda r: r.url.endswith("/managed/suite")) as suite:
                page.locator("#managed-suite").click()
            assert suite.value.status == 200
            page.locator("#managed-start").click()
            started = wait_state(
                f"projects/{pid}/managed", lambda v: v["status"] in {"ready", "failed"}, 300
            )
            assert started["status"] == "ready", started.get("reason")
            event(
                "ready",
                "The model server is ready. The suite was loaded before Start because cases are configuration-bound.",
            )
            page.locator("#model-prompt-form textarea").fill(
                "What is 2 + 2? Answer with only the number."
            )
            with page.expect_response(
                lambda r: r.url.endswith("/model/predict"), timeout=120000
            ) as reply:
                page.get_by_role("button", name="Send to local server").click()
            prediction = reply.value.json()
            assert reply.value.status == 200 and prediction.get("output")
            record["ask"] = prediction
            event(
                "ask",
                "This is an actual Qwen response from the installed application, not the fixture.",
            )
            page.locator("#endpoint-checks > summary").click()
            page.locator("#model-evaluate").click()
            baseline = wait_state(
                f"projects/{pid}/model",
                lambda v: (
                    (v["model_endpoint"].get("evaluation") or {}).get("status") == "completed"
                ),
            )
            record["baseline"] = baseline["model_endpoint"]["evaluation"]
            event(
                "evaluated",
                "The displayed rule results are actual. Failed answers are retained; rule agreement is not semantic quality.",
            )
            page.locator("#model-evaluate").click()
            wait_state(
                f"projects/{pid}/model",
                lambda v: (v["model_endpoint"].get("evaluation") or {}).get("status") == "running",
            )
            scope = hashlib.sha256(os.path.normcase(str(workspace.resolve())).encode()).hexdigest()[
                :16
            ]
            docker = shutil.which("docker")
            assert docker
            names = subprocess.check_output(  # noqa: S603 -- exact owned workspace/project/role
                [
                    docker,
                    "ps",
                    "--filter",
                    "label=furnace.managed.workspace=" + scope,
                    "--filter",
                    "label=furnace.managed.project=" + pid,
                    "--filter",
                    "label=furnace.managed.role=model",
                    "--format",
                    "{{.Names}}",
                ],
                text=True,
            ).split()
            assert len(names) == 1 and names[0].startswith("furnace-model-")
            subprocess.run([docker, "kill", names[0]], check=True, capture_output=True)  # noqa: S603 -- deliberate failure injection into the one verified demo container
            interrupted = wait_state(
                f"projects/{pid}/model",
                lambda v: (
                    (v["model_endpoint"].get("evaluation") or {}).get("status") == "interrupted"
                ),
            )
            record["interrupted"] = interrupted["model_endpoint"]["evaluation"]
            assert any(case["status"] == "error" for case in record["interrupted"]["results"])
            event(
                "crashed",
                "Deliberately killed only this model container during evaluation. The interrupted attempt stays in history.",
            )
            # This UI deliberately refreshes health on request; do not pretend it
            # has a live alerting subsystem or restart against stale ready state.
            with page.expect_response(lambda r: r.url.endswith("/managed/observe")):
                page.locator("#managed-observe-refresh").click()
            with page.expect_response(lambda r: r.url.endswith("/api/projects")):
                page.locator("#model-refresh").click()
            page.locator("#managed-consent").check()
            page.locator("#managed-start").click()
            wait_state(f"projects/{pid}/managed", lambda v: v["status"] == "ready", 300)
            page.locator("#model-evaluate").click()
            restarted = wait_state(
                f"projects/{pid}/model",
                lambda v: (
                    (v["model_endpoint"].get("evaluation") or {}).get("status") == "completed"
                    and v["model_endpoint"]["evaluation"]["run_id"] != record["baseline"]["run_id"]
                ),
            )
            record["restart"] = restarted["model_endpoint"]
            repro = record["restart"]["reproducibility"]
            assert repro["reference_launch_id"] != repro["current_launch_id"]
            event(
                "reproducibility",
                f"Explicit restart and a new completed batch. Actual comparison: {repro['identical']} of {repro['compared']} outputs identical. Identity is not correctness.",
            )
            video = page.video
            context.close()
            assert video
            shutil.copy2(video.path(), args.out / "studio-journey.webm")
            record["result"] = "passed"
            browser.close()
    finally:
        if child.stdin:
            with contextlib.suppress(OSError):
                child.stdin.write("quit\n")
                child.stdin.flush()
        stdout, stderr = child.communicate(timeout=90)
        record["quit_and_lease_released"] = (
            child.returncode == 0 and '"lease_released": true' in stdout
        )
        if not record["quit_and_lease_released"]:
            record["result"] = "failed"
        (args.out / "record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    assert record["result"] == "passed", stderr[-500:]
    print(args.out / "record.json")


if __name__ == "__main__":
    main()
