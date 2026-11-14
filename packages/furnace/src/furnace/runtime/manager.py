"""Workspace-scoped Docker workers. No user code, weights or credentials are mounted."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from furnace.sandbox.docker_sandbox import DOCKERFILE, IMAGE

CLIENT = """import socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(6)
s.connect('/tmp/furnace-worker.sock')
s.sendall(sys.stdin.buffer.read())
data=bytearray()
while not data.endswith(b'\\n'):
 chunk=s.recv(4096)
 if not chunk or len(data)+len(chunk)>32768: raise RuntimeError('invalid worker response')
 data.extend(chunk)
sys.stdout.buffer.write(data)
"""


class RuntimeFault(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class RuntimeManager:
    def __init__(self, workspace: Path):
        self.scope = hashlib.sha256(
            os.path.normcase(str(workspace.resolve())).encode()
        ).hexdigest()[:16]
        self._locks: dict[str, threading.RLock] = {}
        self._lock = threading.Lock()
        self._environment: dict[str, str] | None = None

    def lock_for(self, project_id: str) -> threading.RLock:
        if not re.fullmatch(r"[a-f0-9]{32}", project_id):
            raise RuntimeFault("invalid_project")
        with self._lock:
            return self._locks.setdefault(project_id, threading.RLock())

    def name(self, project_id: str) -> str:
        self.lock_for(project_id)
        return f"furnace-studio-{self.scope}-{project_id}"

    def docker_environment(self) -> dict[str, str]:
        with self._lock:
            if self._environment is not None:
                return self._environment
            environment = os.environ.copy()
            endpoint = environment.get("DOCKER_HOST")
            if not endpoint:
                executable = shutil.which("docker")
                if executable is None:
                    raise RuntimeFault("docker_unavailable")
                try:
                    result = subprocess.run(  # noqa: S603 -- resolved Docker, fixed context inspection
                        [
                            executable,
                            "context",
                            "inspect",
                            "--format",
                            "{{json .Endpoints.docker.Host}}",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode:
                        raise RuntimeFault("docker_context_unavailable")
                    endpoint = json.loads(result.stdout)
                except (OSError, subprocess.TimeoutExpired, ValueError):
                    raise RuntimeFault("docker_context_unavailable") from None
            if not isinstance(endpoint, str) or not endpoint.startswith(("unix://", "npipe://")):
                raise RuntimeFault("remote_docker_refused")
            environment["DOCKER_HOST"] = endpoint
            for name in ("DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
                environment.pop(name, None)
            self._environment = environment
            return environment

    def _docker(
        self, *args: str, timeout: float = 5, data: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        executable = shutil.which("docker")
        if executable is None:
            raise RuntimeFault("docker_unavailable")
        try:
            result = subprocess.run(  # noqa: S603 -- resolved Docker, fixed argv; never a shell
                [executable, *args],
                input=data,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                env=self.docker_environment(),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeFault("timeout") from None
        except OSError:
            raise RuntimeFault("docker_unavailable") from None
        if check and result.returncode:
            raise RuntimeFault(
                "docker_unavailable" if args[0] == "version" else "docker_operation_failed"
            )
        return result

    def inspect(self, project_id: str) -> dict[str, Any] | None:
        # Check the daemon first: a failed inspect is not proof a worker is absent.
        self._docker("version", "--format", "{{.Server.Version}}", timeout=3)
        result = self._docker(
            "inspect", "--format", "{{json .}}", self.name(project_id), check=False
        )
        if result.returncode:
            listed = self._docker(
                "ps",
                "--all",
                "--filter",
                f"name=^/{self.name(project_id)}$",
                "--format",
                "{{.Names}}",
            )
            if listed.stdout.strip():
                raise RuntimeFault("worker_inspection_failed")
            return None
        try:
            info = json.loads(result.stdout)
            labels = info["Config"]["Labels"] or {}
            if (
                labels.get("furnace.studio.workspace") != self.scope
                or labels.get("furnace.studio.project") != project_id
            ):
                raise RuntimeFault("ownership_mismatch")
            return info
        except (ValueError, KeyError, TypeError):
            raise RuntimeFault("invalid_docker_response") from None

    def prepare(self) -> None:
        self._docker("version", "--format", "{{.Server.Version}}", timeout=3)
        if self._docker("image", "inspect", IMAGE, check=False).returncode:
            self._docker(
                "build", "-t", IMAGE, "-f", str(DOCKERFILE), str(DOCKERFILE.parent), timeout=900
            )

    def readiness(self) -> dict[str, Any]:
        """Read-only local prerequisite check; never pull, build or start a worker."""
        try:
            operating_system = self._docker(
                "version", "--format", "{{.Server.Os}}", timeout=3
            ).stdout.strip()
            if operating_system != "linux":
                return {"status": "unavailable", "code": "linux_containers_required"}
            image = self._docker("image", "inspect", IMAGE, check=False)
            if image.returncode:
                listed = self._docker(
                    "image", "ls", "--filter", f"reference={IMAGE}", "--format", "{{.ID}}"
                )
                if listed.stdout.strip():
                    raise RuntimeFault("image_inspection_failed")
            return {
                "status": "ready" if image.returncode == 0 else "needs_preparation",
                "code": "image_ready" if image.returncode == 0 else "image_not_prepared",
            }
        except RuntimeFault as exc:
            return {"status": "unavailable", "code": exc.code}

    def stop(self, project_id: str) -> None:
        with self.lock_for(project_id):
            if self.inspect(project_id) is not None:
                self._docker("rm", "--force", self.name(project_id))

    def _exchange(self, project_id: str, request: dict[str, Any], timeout: float) -> dict[str, Any]:
        result = self._docker(
            "exec",
            "--interactive",
            self.name(project_id),
            "python",
            "-I",
            "-c",
            CLIENT,
            timeout=timeout,
            data=json.dumps(request) + "\n",
        )
        if len(result.stdout.encode()) > 32768:
            raise RuntimeFault("invalid_worker_response")
        try:
            value = json.loads(result.stdout)
            if not isinstance(value, dict):
                raise ValueError("object required")
            return value
        except ValueError:
            raise RuntimeFault("invalid_worker_response") from None

    def start(self, project_id: str) -> dict[str, Any]:
        with self.lock_for(project_id):
            old = self.inspect(project_id)
            if old is not None:
                if old["State"]["Running"]:
                    health = self._exchange(project_id, {"operation": "health"}, timeout=3)
                    if health.get("ready") is True:
                        return {
                            "status": "ready",
                            "container_id": old["Id"],
                            "adapter": "framework_fixture",
                            "model_execution": False,
                        }
                self.stop(project_id)
            if self._docker("image", "inspect", IMAGE, check=False).returncode:
                raise RuntimeFault("image_not_prepared")
            worker = Path(__file__).with_name("worker.py").resolve()
            if "," in str(worker):
                raise RuntimeFault("unsupported_install_path")
            self._docker(
                "run",
                "--detach",
                "--name",
                self.name(project_id),
                "--label",
                f"furnace.studio.workspace={self.scope}",
                "--label",
                f"furnace.studio.project={project_id}",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--user",
                "10001:10001",
                "--memory",
                "256m",
                "--cpus",
                "1",
                "--pids-limit",
                "64",
                "--init",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=16m,mode=1777",  # noqa: S108 -- isolated container tmpfs
                "--mount",
                f"type=bind,source={worker},target=/worker.py,readonly",
                "--entrypoint",
                "python",
                IMAGE,
                "-I",
                "-u",
                "/worker.py",
                timeout=15,
            )
            try:
                for _ in range(20):
                    try:
                        health = self._exchange(project_id, {"operation": "health"}, timeout=1)
                        if (
                            health.get("ready") is True
                            and health.get("adapter") == "framework_fixture"
                        ):
                            info = self.inspect(project_id)
                            if info and info["State"]["Running"]:
                                return {
                                    "status": "ready",
                                    "container_id": info["Id"],
                                    "adapter": "framework_fixture",
                                    "model_execution": False,
                                }
                    except RuntimeFault:
                        pass
                    time.sleep(0.1)
                raise RuntimeFault("worker_startup_failed")
            except RuntimeFault:
                self.stop(project_id)
                raise

    def predict(
        self, project_id: str, value: str, timeout_s: float = 5, operation: str = "predict"
    ) -> dict[str, Any]:
        if operation not in {"predict", "error", "timeout", "crash"}:
            raise RuntimeFault("invalid_operation")
        if not isinstance(value, str) or not 1 <= len(value) <= 4000:
            raise RuntimeFault("invalid_input")
        with self.lock_for(project_id):
            started = time.monotonic()
            info = self.inspect(project_id)
            if info is None or not info["State"]["Running"]:
                raise RuntimeFault("worker_not_running")
            try:
                result = self._exchange(
                    project_id,
                    {"operation": operation, "input": value},
                    timeout=max(0.1, min(timeout_s, 5)),
                )
                if result.get("error"):
                    raise RuntimeFault("worker_error")
                if (
                    not isinstance(result.get("output"), str)
                    or result.get("adapter") != "framework_fixture"
                    or result.get("model_execution") is not False
                ):
                    raise RuntimeFault("invalid_worker_response")
                return {
                    **result,
                    "request_id": hashlib.sha256(
                        f"{self.scope}:{time.monotonic_ns()}".encode()
                    ).hexdigest()[:24],
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                }
            except RuntimeFault:
                # Stop actual execution on timeout/crash/error, not only its HTTP waiter.
                self.stop(project_id)
                raise
