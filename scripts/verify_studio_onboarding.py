"""Installed-bundle onboarding smoke. Run in a disposable Linux Python/uv environment."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-empty-cache", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux":
        raise SystemExit("Run this clean-environment smoke inside a disposable Linux container")
    if args.expect_empty_cache:
        cache = Path(os.environ["UV_CACHE_DIR"])
        if cache.exists() and any(cache.iterdir()):
            raise SystemExit("The requested clean uv cache is not empty")
    with tempfile.TemporaryDirectory(prefix="furnace-onboarding-") as directory:
        root = Path(directory)
        install = root / "installed"
        with zipfile.ZipFile(args.bundle) as archive:
            archive.extractall(install)
        missing_uv = subprocess.run(  # noqa: S603 -- own generated launcher; empty executable path
            [sys.executable, str(install / "launch.py")],
            env={**os.environ, "PATH": ""},
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert missing_uv.returncode != 0 and "Furnace needs uv" in missing_uv.stderr
        assert "Traceback" not in missing_uv.stderr
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        workspace = root / "workspace"
        process: subprocess.Popen | None = None
        session = ""

        def launch(label: str) -> str:
            nonlocal process
            stdout = root / (label + ".out")
            stderr = root / (label + ".err")
            with stdout.open("w") as out, stderr.open("w") as err:
                process = subprocess.Popen(  # noqa: S603 -- own generated launcher; no shell
                    [
                        sys.executable,
                        str(install / "launch.py"),
                        "--no-browser",
                        "--workspace",
                        str(workspace),
                        "--port",
                        str(port),
                    ],
                    cwd=install,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                )
            for _ in range(360):
                if process.poll() is not None:
                    raise RuntimeError("Installed launch failed: " + stderr.read_text()[-4000:])
                match = re.search(r"#session=([a-zA-Z0-9_-]+)", stdout.read_text())
                if match:
                    try:
                        request = urllib.request.Request(  # noqa: S310 -- generated loopback URL only
                            base + "/api/projects", headers={"X-Furnace-Session": match[1]}
                        )
                        with urllib.request.urlopen(request, timeout=2) as response:  # noqa: S310 -- generated loopback URL only
                            if response.status == 200:
                                return match[1]
                    except OSError:
                        pass
                time.sleep(0.5)
            raise RuntimeError("Installed startup timed out: " + stderr.read_text()[-4000:])

        def stop() -> None:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                    raise RuntimeError("Installed application did not shut down normally") from None

        def api(path: str, method: str = "GET", data: dict | None = None, token: str | None = None):
            request = urllib.request.Request(  # noqa: S310 -- generated loopback URL only
                base + "/api/" + path,
                method=method,
                data=json.dumps(data).encode() if data is not None else None,
                headers={
                    "X-Furnace-Session": token or session,
                    "Content-Type": "application/json",
                    "Origin": base,
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 -- generated loopback URL only
                raw = response.read()
                return (
                    raw
                    if "zip" in response.headers.get("content-type", "")
                    else json.loads(raw)
                    if raw
                    else None
                )

        try:
            began = time.monotonic()
            session = launch("first")
            first_start_seconds = round(time.monotonic() - began, 2)
            system = api("system")
            assert (
                system["workspace"] == "available" and system["runtime"]["status"] == "unavailable"
            )
            assert system["runtime"]["code"] == "docker_unavailable"
            with urllib.request.urlopen(base + "/assets/studio-state.mjs", timeout=5) as response:  # noqa: S310 -- generated loopback URL only
                assert "javascript" in response.headers["content-type"]
                assert b"journeyFor" in response.read()
            example = api("examples/framework", "POST")
            assert example["origin"] == "guided_example" and example["runtime"] == "not_connected"
            assert len(example["cases"]) == 2 and all(
                case["status"] == "not_run" for case in example["cases"]
            )
            assert not example["assessment"]["execution_performed"]
            pid = example["id"]
            api(
                f"projects/{pid}/contract",
                "PUT",
                {"architecture": "Preserved metadata only", "notes": "No inference has run"},
            )
            with zipfile.ZipFile(io.BytesIO(api(f"projects/{pid}/kit", "POST"))) as kit:
                assert len(kit.namelist()) == 6
                assert (
                    json.loads(kit.read("model-contract.json"))["architecture"]
                    == "Preserved metadata only"
                )
                assert json.loads(kit.read("workspace-plan.json"))["evaluation"] is None
            old_token = session
            stop()
            session = launch("restarted")
            assert old_token != session
            try:
                api("projects", token=old_token)
                raise AssertionError("Old session was accepted")
            except urllib.error.HTTPError as error:
                assert error.code == 401
            restored = api("examples/framework", "POST")
            assert (
                restored["id"] == pid
                and restored["contract"]["architecture"] == "Preserved metadata only"
            )
            assert len(api("projects")) == 1
            api(f"projects/{pid}", "DELETE")
            assert api("projects") == []
            report = {
                "bundle_sha256": hashlib.sha256(args.bundle.read_bytes()).hexdigest(),
                "platform": sys.platform,
                "uid": os.getuid(),
                "empty_cache_required": args.expect_empty_cache,
                "first_start_seconds_including_install": first_start_seconds,
                "missing_uv_guidance": "passed",
                "workspace_without_docker": "passed",
                "installed_module_assets": "passed",
                "guided_example_and_export": "passed",
                "persistence_and_token_rotation": "passed",
                "model_execution": False,
                "gpu_execution": False,
            }
            if args.output:
                args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
        finally:
            stop()


if __name__ == "__main__":
    main()
