"""Operate an adapter's model server in an isolated local Docker container.

Topology per project: the model container sits alone on an `--internal` Docker
network (external routes restricted; bridge host services are not fully isolated). A minimal relay container joins
that network and the default bridge and is the only thing published, on
127.0.0.1 with a Docker-assigned port. The model container runs as a non-root
user with a read-only root filesystem, no capabilities, a memory limit without
swap, CPU and PID limits, read-only weights and a per-launch API key excluded
from Studio's database/logs/exports. Docker also retains it in container configuration.

Docker owns the containers, so they outlive a crashed Studio; `recover()` removes
every container and network labelled for this workspace on the next start.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from furnace.runtime.adapter import LaunchSpec
from furnace.runtime.catalog import RELAY_IMAGE

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_METRIC = re.compile(r"^([a-zA-Z_:][\w:]*)(?:\{[^}]*\})?\s+([-+0-9.eE]+|NaN)$")
LOG_LIMIT = 32768


class ServingFault(Exception):
    def __init__(self, code: str, detail: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


def workspace_scope(workspace: Path) -> str:
    return hashlib.sha256(os.path.normcase(str(workspace.resolve())).encode()).hexdigest()[:16]


def _run_cancellable(
    command: list[str], env: dict[str, str], timeout: float, cancel: threading.Event
) -> subprocess.CompletedProcess[str]:
    """Cancel only our CLI process and reap it before its preparation worker exits."""
    if cancel.is_set():
        raise ServingFault("preparation_cancelled")
    deadline = time.monotonic() + timeout
    with subprocess.Popen(  # noqa: S603 -- resolved executable and authored argument list
        command,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    ) as process:
        try:
            while True:
                if cancel.is_set():
                    raise ServingFault("preparation_cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ServingFault("docker_timeout")
                try:
                    stdout, stderr = process.communicate(timeout=min(0.2, remaining))
                    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


class Supervisor:
    def __init__(self, workspace: Path, docker_env: Callable[[], dict[str, str]]):
        self.scope = workspace_scope(workspace)
        self._docker_env = docker_env
        self._keys: dict[str, str] = {}
        self._ports: dict[str, int] = {}
        self._guard = threading.Lock()

    # -- docker plumbing -------------------------------------------------------------
    def names(self, pid: str) -> dict[str, str]:
        if not re.fullmatch(r"[a-f0-9]{32}", pid):
            raise ServingFault("invalid_project")
        base = f"{self.scope}-{pid}"
        return {
            "model": f"furnace-model-{base}",
            "relay": f"furnace-relay-{base}",
            "network": f"furnace-net-{base}",
        }

    def _docker(
        self,
        *args: str,
        timeout: float = 30,
        check: bool = True,
        extra_env: dict[str, str] | None = None,
        cancel: threading.Event | None = None,
    ) -> subprocess.CompletedProcess[str]:
        executable = shutil.which("docker")
        if executable is None:
            raise ServingFault("docker_unavailable")
        env = dict(self._docker_env())
        env.update(extra_env or {})
        try:
            if cancel is not None:
                result = _run_cancellable([executable, *args], env, timeout, cancel)
            else:
                result = subprocess.run(  # noqa: S603 -- resolved Docker, fixed argv, never a shell
                    [executable, *args],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    check=False,
                    env=env,
                )
        except subprocess.TimeoutExpired:
            raise ServingFault("docker_timeout") from None
        except OSError:
            raise ServingFault("docker_unavailable") from None
        if check and result.returncode:
            raise ServingFault("docker_operation_failed", {"operation": args[0]})
        return result

    def _labels(self, pid: str, role: str, extra: dict[str, str]) -> list[str]:
        values = {
            "furnace.managed.workspace": self.scope,
            "furnace.managed.project": pid,
            "furnace.managed.role": role,
            **extra,
        }
        return [arg for key, value in values.items() for arg in ("--label", f"{key}={value}")]

    def daemon(self) -> dict[str, Any]:
        """Read-only prerequisite check: engine OS and whether a GPU runtime is offered."""
        try:
            info = json.loads(self._docker("info", "--format", "{{json .}}", timeout=10).stdout)
        except (ServingFault, ValueError):
            return {"status": "unavailable", "gpu_runtime": False}
        runtimes = info.get("Runtimes") or {}
        return {
            "status": "ready" if info.get("OSType") == "linux" else "linux_containers_required",
            "gpu_runtime": "nvidia" in runtimes,
            "cpus": info.get("NCPU"),
            "memory_bytes": info.get("MemTotal"),
        }

    def image_present(self, image: str) -> bool:
        return self._docker("image", "inspect", image, check=False, timeout=15).returncode == 0

    def pull(
        self, image: str, timeout: float = 1800, cancel: threading.Event | None = None
    ) -> None:
        if re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            # A locally built image cannot be pulled; it must already be present.
            if not self.image_present(image):
                raise ServingFault("local_image_not_present")
            return
        if "@sha256:" not in image:
            raise ServingFault("image_not_pinned")
        if not self.image_present(image):
            self._docker("pull", "--quiet", image, timeout=timeout, cancel=cancel)
        if not self.image_present(image):
            raise ServingFault("image_pull_unconfirmed")

    # -- lifecycle -------------------------------------------------------------------
    def start(self, pid: str, spec: LaunchSpec, labels: dict[str, str]) -> dict[str, Any]:
        names = self.names(pid)
        self.stop(pid)
        for mount in spec.mounts:
            if "," in str(mount.source) or not mount.source.exists():
                raise ServingFault("mount_source_invalid")
        for image in (spec.image, RELAY_IMAGE):
            if not self.image_present(image):
                raise ServingFault("image_not_prepared")
        launch = uuid.uuid4().hex
        key = secrets.token_urlsafe(32)
        extra = {**spec.labels, **labels, "furnace.managed.launch": launch}
        self._docker(
            "network", "create", "--internal", *self._labels(pid, "network", extra),
            names["network"],
        )  # fmt: skip
        try:
            args = [
                "run", "--detach", "--name", names["model"],
                *self._labels(pid, "model", extra),
                "--network", names["network"],
                "--read-only",
                "--tmpfs", f"/tmp:rw,noexec,nosuid,size={spec.tmpfs_mb}m",  # noqa: S108 -- container tmpfs
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--user", "10001:10001",
                "--memory", f"{spec.memory_mb}m",
                "--memory-swap", f"{spec.memory_mb}m",
                "--cpus", str(spec.cpus),
                "--pids-limit", str(spec.pids),
                "--ulimit", "nofile=4096:4096",
                "--env", spec.secret_env,  # value comes from the CLI environment, not argv
            ]  # fmt: skip
            if spec.gpu:
                args += ["--gpus", "all"]
            for mount in spec.mounts:
                args += [
                    "--mount",
                    f"type=bind,source={mount.source},target={mount.target},readonly",
                ]
            if spec.entrypoint:
                args += ["--entrypoint", spec.entrypoint]
            self._docker(
                *args, spec.image, *spec.command, timeout=120, extra_env={spec.secret_env: key}
            )
            self._docker(
                "create", "--name", names["relay"],
                *self._labels(pid, "relay", extra),
                "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--user", "10001:10001",
                "--memory", "64m", "--cpus", "0.5", "--pids-limit", "64",
                "--publish", f"127.0.0.1::{spec.internal_port}",
                RELAY_IMAGE,
                f"TCP-LISTEN:{spec.internal_port},fork,reuseaddr",
                f"TCP:{names['model']}:{spec.internal_port}",
                timeout=60,
            )  # fmt: skip
            self._docker("network", "connect", names["network"], names["relay"])
            self._docker("start", names["relay"])
            published = self._docker("port", names["relay"], f"{spec.internal_port}/tcp").stdout
            match = re.search(r"127\.0\.0\.1:(\d+)", published)
            if not match:
                raise ServingFault("relay_port_unavailable")
            port = int(match.group(1))
        except ServingFault:
            with contextlib.suppress(ServingFault):
                self.stop(pid)
            raise
        with self._guard:
            self._keys[pid], self._ports[pid] = key, port
        return {
            "launch_id": launch,
            "port": port,
            "base_url": f"http://127.0.0.1:{port}/v1",
            "started_at": datetime.now(UTC).isoformat(),
        }

    def wait_ready(
        self,
        pid: str,
        spec: LaunchSpec,
        cancel: threading.Event | None = None,
        on_state: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        began = time.monotonic()
        port = self.port(pid)
        if port is None:
            raise ServingFault("server_not_started")
        reported = ""
        while True:
            if cancel is not None and cancel.is_set():
                raise ServingFault("start_cancelled")
            state = self.container_state(pid)
            if not state["running"]:
                raise ServingFault(state["failure"] or "server_exited", state)
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{port}{spec.health_path}", timeout=2, trust_env=False
                )
                if response.status_code == 200 and response.json().get("status") == "ok":
                    return {"load_seconds": round(time.monotonic() - began, 2)}
                if response.status_code == 500:
                    raise ServingFault("server_load_failed", {"health_status": 500})
                phase = "loading" if response.status_code == 503 else "starting"
            except (httpx.HTTPError, ValueError):
                phase = "starting"
            if phase != reported and on_state is not None:
                on_state(phase)
                reported = phase
            if cancel is not None and cancel.is_set():
                raise ServingFault("start_cancelled")
            if time.monotonic() - began > spec.load_timeout_s:
                raise ServingFault("server_load_timeout")
            time.sleep(0.5)

    def container_state(self, pid: str) -> dict[str, Any]:
        names = self.names(pid)
        result = self._docker("inspect", "--format", "{{json .}}", names["model"], check=False)
        if result.returncode:
            return {"running": False, "present": False, "failure": "server_container_missing"}
        try:
            info = json.loads(result.stdout)
            labels = info["Config"]["Labels"] or {}
            if (
                labels.get("furnace.managed.workspace") != self.scope
                or labels.get("furnace.managed.project") != pid
            ):
                raise ServingFault("ownership_mismatch")
            state = info["State"]
        except (ValueError, KeyError, TypeError):
            raise ServingFault("invalid_docker_response") from None
        failure = None
        if not state.get("Running"):
            failure = (
                "server_out_of_memory"
                if state.get("OOMKilled")
                else f"server_exited_{state.get('ExitCode')}"
            )
        relay = self._docker(
            "inspect", "--format", "{{.State.Running}}", names["relay"], check=False
        )
        relay_running = relay.returncode == 0 and relay.stdout.strip() == "true"
        if failure is None and not relay_running:
            failure = "relay_not_running"
        return {
            "running": failure is None,
            "present": True,
            "failure": failure,
            "exit_code": state.get("ExitCode"),
            "oom_killed": bool(state.get("OOMKilled")),
            "started_at": state.get("StartedAt"),
            "launch_id": labels.get("furnace.managed.launch"),
            "container_id": info.get("Id", "")[:12],
            "networks": sorted((info.get("NetworkSettings") or {}).get("Networks") or {}),
        }

    def stop(self, pid: str) -> None:
        names = self.names(pid)
        with self._guard:
            self._keys.pop(pid, None)
            self._ports.pop(pid, None)
        for role in ("relay", "model"):
            self._remove_owned("container", names[role], pid)
        self._remove_owned("network", names["network"], pid)

    def _remove_owned(self, kind: str, name: str, pid: str) -> None:
        found = self._docker(kind, "inspect", "--format", "{{json .Labels}}" if kind == "network"
                             else "{{json .Config.Labels}}", name, check=False)  # fmt: skip
        if found.returncode:
            if re.search(r"No such (?:container|network|object):", found.stderr) or (
                kind == "network" and f"network {name} not found" in found.stderr
            ):
                return
            raise ServingFault("cleanup_unconfirmed")
        try:
            labels = json.loads(found.stdout) or {}
        except ValueError:
            raise ServingFault("invalid_docker_response") from None
        if (
            labels.get("furnace.managed.workspace") != self.scope
            or labels.get("furnace.managed.project") != pid
        ):
            raise ServingFault("ownership_mismatch")
        if kind == "container":
            self._docker("rm", "--force", name, timeout=60)
        else:
            self._docker("network", "rm", name, timeout=60)

    def recover(self) -> list[str]:
        """Remove every managed container/network of this workspace (orphans after a crash)."""
        removed: list[str] = []
        label = f"label=furnace.managed.workspace={self.scope}"
        listed = self._docker("ps", "--all", "--filter", label, "--format", "{{.Names}}")
        for name in [n for n in listed.stdout.split() if n]:
            self._docker("rm", "--force", name, timeout=60)
            removed.append(name)
        networks = self._docker("network", "ls", "--filter", label, "--format", "{{.Name}}")
        for name in [n for n in networks.stdout.split() if n]:
            self._docker("network", "rm", name, timeout=60)
            removed.append(name)
        with self._guard:
            self._keys.clear()
            self._ports.clear()
        return removed

    # -- observation -----------------------------------------------------------------
    def api_key(self, pid: str) -> str | None:
        with self._guard:
            return self._keys.get(pid)

    def port(self, pid: str) -> int | None:
        with self._guard:
            return self._ports.get(pid)

    def logs(self, pid: str, tail: int = 200) -> str:
        result = self._docker(
            "logs", "--tail", str(max(1, min(tail, 1000))), self.names(pid)["model"],
            check=False, timeout=15,
        )  # fmt: skip
        text = _ANSI.sub("", (result.stdout or "") + (result.stderr or ""))
        key = self.api_key(pid)
        if key:
            text = text.replace(key, "[redacted]")
        return text[-LOG_LIMIT:]

    def gpu(self) -> dict[str, Any]:
        """Host GPU state from the driver's nvidia-smi; empty when no NVIDIA driver is present."""
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return {}
        try:
            result = subprocess.run(  # noqa: S603 -- driver tool, fixed read-only query
                [
                    executable,
                    "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            name, used, total, utilization, temperature = [
                v.strip() for v in result.stdout.splitlines()[0].split(",")
            ]
            return {
                "name": name,
                "memory_used_mib": int(used),
                "memory_total_mib": int(total),
                "utilization_percent": int(utilization),
                "temperature_c": int(temperature),
            }
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            return {}

    def stats(self, pid: str) -> dict[str, Any]:
        result = self._docker(
            "stats", "--no-stream", "--format", "{{json .}}", self.names(pid)["model"],
            check=False, timeout=20,
        )  # fmt: skip
        try:
            raw = json.loads(result.stdout.strip().splitlines()[0])
        except (ValueError, IndexError):
            return {}
        return {
            "cpu_percent": raw.get("CPUPerc"),
            "memory": raw.get("MemUsage"),
            "memory_percent": raw.get("MemPerc"),
            "pids": raw.get("PIDs"),
        }

    def metrics(self, pid: str) -> dict[str, float]:
        port, key = self.port(pid), self.api_key(pid)
        if port is None or key is None:
            return {}
        try:
            response = httpx.get(
                f"http://127.0.0.1:{port}/metrics",
                headers={"Authorization": f"Bearer {key}"},
                timeout=3,
                trust_env=False,
            )
        except httpx.HTTPError:
            return {}
        if response.status_code != 200:
            return {}
        values: dict[str, float] = {}
        for line in response.text[:65536].splitlines():
            match = _METRIC.match(line.strip())
            if match and len(values) < 64:
                with contextlib.suppress(ValueError):
                    values[match.group(1)] = float(match.group(2))
        return values
