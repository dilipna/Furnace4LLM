"""Bundle/source onboarding: disposable Linux container or isolated native Windows run."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
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
    parser.add_argument("bundle", type=Path, nargs="?")
    parser.add_argument(
        "--source", type=Path, help="Checkout to sync and launch using documented uv commands"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-empty-cache", action="store_true")
    parser.add_argument("--connector", action="store_true", help="Exercise installed endpoint API")
    parser.add_argument("--browser", action="store_true", help="Also run isolated Chromium checks")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if (args.bundle is None) == (args.source is None):
        parser.error("Choose a bundle ZIP or --source CHECKOUT")
    if sys.platform not in {"linux", "win32"}:
        raise SystemExit("This verifier currently supports Linux and Windows only")
    if args.expect_empty_cache:
        cache = Path(os.environ["UV_CACHE_DIR"])
        if cache.exists() and any(cache.iterdir()):
            raise SystemExit("The requested clean uv cache is not empty")
    with tempfile.TemporaryDirectory(prefix="furnace-onboarding-") as directory:
        root = Path(directory)
        if args.source:
            install = args.source.resolve()
            if args.expect_empty_cache and (install / ".venv").exists():
                raise SystemExit("Clean source verification needs a checkout without .venv")
            git = shutil.which("git")
            uv = shutil.which("uv")
            if not git or not uv:
                raise SystemExit("Source setup requires Git and uv")
            manifest = {
                "source_commit": subprocess.check_output(  # noqa: S603 -- resolved Git, fixed read-only arguments
                    [git, "rev-parse", "HEAD"], cwd=install, text=True
                ).strip(),
                "source_dirty": bool(
                    subprocess.check_output(  # noqa: S603 -- resolved Git, fixed read-only arguments
                        [git, "status", "--porcelain"], cwd=install, text=True
                    ).strip()
                ),
            }
            launch_prefix = [uv, "run", "furnace", "studio"]
        else:
            install = root / "installed"
            with zipfile.ZipFile(args.bundle) as archive:
                archive.extractall(install)
            manifest = json.loads((install / "manifest.json").read_text(encoding="utf-8"))
            missing_uv = subprocess.run(  # noqa: S603 -- own generated launcher; empty executable path
                [sys.executable, str(install / "launch.py")],
                env={**os.environ, "PATH": ""},
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert missing_uv.returncode != 0 and "Furnace needs uv" in missing_uv.stderr
            assert "Traceback" not in missing_uv.stderr
            launch_prefix = [sys.executable, str(install / "launch.py")]
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        workspace = root / "workspace"
        process: subprocess.Popen | None = None
        session = ""
        launch_env = {**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"}
        launch_env.pop("PYTHONPATH", None)
        if sys.platform == "win32":
            uv = shutil.which("uv")
            if uv is None:
                raise SystemExit("Install uv before running the Windows verifier")
            # Exercise the workspace without Docker discovery; do not alter system PATH.
            launch_env["PATH"] = os.pathsep.join(
                [str(Path(uv).parent), str(Path(sys.executable).parent)]
            )

        def launch(label: str) -> str:
            nonlocal process
            if args.source and label == "first":
                subprocess.run(  # noqa: S603 -- resolved uv, documented fixed setup command
                    [launch_prefix[0], "sync", "--frozen"],
                    cwd=install,
                    env=launch_env,
                    check=True,
                    timeout=180,
                )
            stdout = root / (label + ".out")
            stderr = root / (label + ".err")
            with (
                stdout.open("w", encoding="utf-8") as out,
                stderr.open("w", encoding="utf-8") as err,
            ):
                process = subprocess.Popen(  # noqa: S603 -- own generated launcher; no shell
                    [
                        *launch_prefix,
                        "--no-browser",
                        "--workspace",
                        str(workspace),
                        "--port",
                        str(port),
                    ],
                    cwd=install,
                    stdout=out,
                    stderr=err,
                    env=launch_env,
                    start_new_session=sys.platform != "win32",
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0,
                )
            for _ in range(360):
                if process.poll() is not None:
                    raise RuntimeError(
                        "Installed launch failed: "
                        + stderr.read_text(encoding="utf-8", errors="replace")[-4000:]
                    )
                match = re.search(
                    r"#session=([a-zA-Z0-9_-]+)",
                    stdout.read_text(encoding="utf-8", errors="replace"),
                )
                if match:
                    try:
                        request = urllib.request.Request(  # noqa: S310 -- generated loopback URL only
                            base + "/api/projects", headers={"X-Furnace-Session": match[1]}
                        )
                        with opener.open(request, timeout=3) as response:
                            if response.status == 200:
                                return match[1]
                    except OSError:
                        pass
                time.sleep(0.5)
            raise RuntimeError(
                "Installed startup timed out: "
                + stderr.read_text(encoding="utf-8", errors="replace")[-4000:]
            )

        def stop() -> None:
            if process is None:
                return
            if process.poll() is None:
                if sys.platform == "win32":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    if sys.platform == "win32":
                        taskkill = shutil.which("taskkill")
                        if taskkill:
                            subprocess.run(  # noqa: S603 -- only the process created above and its descendants
                                [taskkill, "/PID", str(process.pid), "/T", "/F"],
                                check=False,
                                capture_output=True,
                            )
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                    raise RuntimeError("Installed application did not shut down normally") from None
            deadline = time.monotonic() + 20
            while True:
                try:
                    with opener.open(
                        base + "/healthz", timeout=3 if sys.platform == "win32" else 0.5
                    ) as response:
                        response.read()
                    listening = True
                except urllib.error.HTTPError:
                    listening = True  # Any HTTP response proves the listener still exists.
                except urllib.error.URLError as error:
                    listening = not isinstance(error.reason, ConnectionRefusedError)
                except OSError:
                    listening = True  # Timeout/reset does not prove the port has closed.
                released = True
                if sys.platform == "win32" and (workspace / "studio.lock").exists():
                    import msvcrt

                    try:
                        with (workspace / "studio.lock").open("r+b") as lease:
                            msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
                            lease.seek(0)
                            msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        released = False
                if not listening and released:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "Installed server or workspace lease remained active after shutdown"
                    )
                time.sleep(0.1)

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
            with opener.open(request, timeout=20) as response:
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
            catalog = api("managed/catalog")
            assert catalog["docker"]["status"] == "unavailable"
            assert catalog["models"]
            assert all(
                present is None
                for model in catalog["models"]
                for present in model["images_present"].values()
            )
            with opener.open(base + "/assets/studio-state.mjs", timeout=5) as response:
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
                assert len(kit.namelist()) == 7
                summary = kit.read("evidence-summary.md").decode()
                assert pid in summary and "No saved attempt" in summary
                assert (
                    json.loads(kit.read("model-contract.json"))["architecture"]
                    == "Preserved metadata only"
                )
                snapshot = json.loads(kit.read("workspace-plan.json"))
                assert snapshot["evaluation"] is None
                assert snapshot["provenance"]["project_id"] == pid
                assert snapshot["provenance"]["verification_status"] == "no_current_evidence"
                assert snapshot["provenance"]["model_inference"] is False
            with opener.open(base + "/guide", timeout=5) as response:
                assert b"YOUR_PINNED_MODEL_ID" in response.read()
            old_token = session
            connector = None
            if args.connector or args.browser:
                from studio_connector_checks import verify_connector

                connector = verify_connector(
                    base,
                    session,
                    api,
                    pid,
                    root,
                    browser=args.browser,
                    screenshots=args.screenshots,
                )
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
            if connector:
                endpoint = restored["model_endpoint"]
                assert endpoint["state"]["status"] == "disconnected"
                assert endpoint["evaluation"]["run_id"] == connector["saved_run_id"]
                assert [run["run_id"] for run in endpoint["history"]] == connector[
                    "saved_history_ids"
                ]
                connector["restart_disconnected_and_evidence_preserved"] = "passed"
            api(f"projects/{pid}", "DELETE")
            assert api("projects") == []
            report = {
                "source_commit": manifest.get("source_commit"),
                "source_dirty": manifest.get("source_dirty"),
                "package_version": manifest.get("package_version"),
                "bundle_sha256": hashlib.sha256(args.bundle.read_bytes()).hexdigest()
                if args.bundle
                else None,
                "delivery": "source" if args.source else "bundle",
                "source_sync_frozen": "passed" if args.source else None,
                "platform": sys.platform,
                "python": sys.version.split()[0],
                "outside_repository": args.source is None,
                "guided_workflow": "metadata, contract edit and kit export; no fixture execution",
                "docker_usage": "CLI excluded from child PATH; no fixture execution"
                if sys.platform == "win32"
                else "outer test container only; no Docker CLI/socket in Studio",
                "github_operations": False,
                "real_application_evaluation": False,
                "remote_inference": False,
                "uid": os.getuid() if sys.platform != "win32" else None,
                "shutdown_signal": "CTRL_BREAK_EVENT" if sys.platform == "win32" else "SIGINT",
                "shutdown_port_closed": "passed",
                "shutdown_workspace_released": "passed"
                if sys.platform == "win32"
                else "verified_by_restart",
                "fresh_machine_or_user": False if sys.platform == "win32" else None,
                "empty_cache_required": args.expect_empty_cache,
                "first_start_seconds_including_install": first_start_seconds,
                "missing_uv_guidance": "not_applicable_source_requires_uv"
                if args.source
                else "passed",
                "workspace_without_docker": "passed",
                "catalog_without_docker": "passed; image availability unknown, no execution",
                "installed_module_assets": "passed",
                "guided_example_and_export": "passed",
                "persistence_and_token_rotation": "passed",
                "model_execution": False,
                "gpu_execution": False,
                "connector": connector,
            }
            if args.output:
                args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
        finally:
            stop()


if __name__ == "__main__":
    main()
