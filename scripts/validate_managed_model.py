"""Validate one pinned model through the complete local Studio journey, for real.

Launches an actual Studio process and drives its HTTP API like the UI does:
prepare (pull pinned images, download and verify weights), start the isolated
server, readiness, inference, reference-suite evaluation with rule checks,
reproducibility, a server crash injected mid-evaluation, explicit restart, a
hard Studio crash with recovery on reopen, export checks and stop. Every
observation is written to a JSON record; nothing is simulated.

    uv run python scripts/validate_managed_model.py --model qwen2.5-0.5b-instruct-q8_0 \
        --accelerator cpu --out docs/product/verification/real-model-qwen-cpu.json

Requires local Docker (Linux containers); --accelerator nvidia also needs GPU support.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def check(condition: bool, label: str, record: dict[str, Any]) -> bool:
    record.setdefault("checks", {})[label] = bool(condition)
    if not condition:
        FAILURES.append(label)
        print(f"  FAIL {label}", flush=True)
    else:
        print(f"  ok   {label}", flush=True)
    return condition


def run(*args: str, timeout: float = 60) -> str:
    try:
        result = subprocess.run(  # noqa: S603 -- fixed local tool invocations
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (result.stdout or "").strip()


def environment() -> dict[str, Any]:
    info = json.loads(run("docker", "info", "--format", "{{json .}}") or "{}")
    gpu = run(
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader",
    )
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "furnace_commit": run("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "working_tree_clean": run("git", "-C", str(ROOT), "status", "--porcelain") == "",
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "python": platform.python_version(),
        "docker_server": info.get("ServerVersion"),
        "docker_os": info.get("OperatingSystem"),
        "docker_vm_cpus": info.get("NCPU"),
        "docker_vm_memory_bytes": info.get("MemTotal"),
        "docker_gpu_runtime": "nvidia" in (info.get("Runtimes") or {}),
        "host_gpu": gpu or None,
        "host_cpu": platform.processor(),
    }


def gpu_memory_mib() -> int | None:
    value = run("nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits")
    try:
        return int(value.splitlines()[0])
    except (ValueError, IndexError):
        return None


class Studio:
    def __init__(self, workspace: Path, artifacts: Path, port: int):
        self.workspace, self.artifacts, self.port = workspace, artifacts, port
        self.process: subprocess.Popen[str] | None = None
        self.client: httpx.Client | None = None

    def start(self) -> float:
        began = time.monotonic()
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.process = subprocess.Popen(  # noqa: S603 -- fixed argv for the local Studio
            [
                sys.executable, "-m", "furnace.cli", "studio", "--no-browser",
                "--workspace", str(self.workspace), "--port", str(self.port),
                "--artifacts", str(self.artifacts),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT,
            creationflags=flags, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )  # fmt: skip
        assert self.process.stdout is not None
        token = None
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and token is None:
            line = self.process.stdout.readline()
            if not line and self.process.poll() is not None:
                raise SystemExit("Studio exited during startup")
            match = re.search(r"#session=([\w-]+)", line)
            if match:
                token = match.group(1)
        if token is None:
            raise SystemExit("Studio did not print a session link")
        threading.Thread(target=self._drain, daemon=True).start()
        self.client = httpx.Client(
            base_url=f"http://127.0.0.1:{self.port}",
            headers={"x-furnace-session": token},
            timeout=httpx.Timeout(600.0),
            trust_env=False,
        )
        for _ in range(200):
            with contextlib.suppress(httpx.HTTPError):
                if self.client.get("/healthz").status_code == 200:
                    return round(time.monotonic() - began, 2)
            time.sleep(0.1)
        raise SystemExit("Studio never became healthy")

    def _drain(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for _ in self.process.stdout:
            pass

    def kill_hard(self) -> None:
        """Simulate a crash: no shutdown hooks run."""
        assert self.process is not None
        if os.name == "nt":
            run("taskkill", "/PID", str(self.process.pid), "/T", "/F")
        else:
            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait(timeout=30)

    def stop_gracefully(self) -> None:
        assert self.process is not None
        if os.name == "nt":
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self.process.send_signal(signal.SIGINT)
        try:
            self.process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.kill_hard()

    def api(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        assert self.client is not None
        return self.client.request(method, "/api/" + path, **kwargs)


def model_container(scope_filter: str) -> list[str]:
    return [
        n
        for n in run(
            "docker", "ps", "--all", "--filter", scope_filter, "--format", "{{.Names}}"
        ).split()
        if n
    ]


def wait_status(
    studio: Studio, pid: str, wanted: set[str], timeout: float = 1800
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    view: dict[str, Any] = {}
    while time.monotonic() < deadline:
        view = studio.api("GET", f"projects/{pid}/managed").json()
        if view.get("status") in wanted:
            return view
        time.sleep(1)
    return view


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--accelerator", choices=["cpu", "nvidia"], default="cpu")
    parser.add_argument("--artifacts", type=Path, default=Path.home() / ".furnace" / "artifacts")
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--memory-mb", type=int, default=2048)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fresh-download", action="store_true",
                        help="use an empty artifacts directory and interrupt the first download")  # fmt: skip
    args = parser.parse_args()

    from furnace.runtime.catalog import MODELS
    from furnace.runtime.serving import workspace_scope

    recipe = MODELS[args.model]
    workspace = Path(tempfile.mkdtemp(prefix="furnace-validate-"))
    artifacts = (
        Path(tempfile.mkdtemp(prefix="furnace-artifacts-"))
        if args.fresh_download
        else args.artifacts
    )
    record: dict[str, Any] = {
        "schema": "furnace-real-model-validation-v1",
        "model": args.model,
        "accelerator": args.accelerator,
        "recipe": {
            "repository": recipe.repository,
            "revision": recipe.revision,
            "weights_sha256": recipe.weights.sha256,
            "architecture": recipe.architecture,
            "license": recipe.license,
        },
        "environment": environment(),
        "steps": {},
    }
    steps = record["steps"]
    scope = f"label=furnace.managed.workspace={workspace_scope(workspace)}"
    studio = Studio(workspace, artifacts, args.port)
    print(f"Validating {args.model} on {args.accelerator}; workspace {workspace}", flush=True)
    try:
        steps["studio_start"] = {"seconds": studio.start()}

        project_dir = workspace / "model-project"
        project_dir.mkdir()
        (project_dir / "README.md").write_text(
            f"# {recipe.name}\n\nMetadata-only project folder for validation. Weights are "
            f"pinned by Furnace: {recipe.repository}@{recipe.revision}.\n",
            encoding="utf-8",
        )
        created = studio.api(
            "POST", "projects", json={"name": recipe.name, "path": str(project_dir)}
        )
        pid = created.json()["id"]
        studio.api("PUT", f"projects/{pid}/contract", json={
            "architecture": recipe.architecture[:120], "task": "text_generation",
            "revision": f"{recipe.repository}@{recipe.revision}"[:120], "license": recipe.license,
            "device": "gpu" if args.accelerator == "nvidia" else "cpu",
            "notes": "Validated through the Furnace-operated llama.cpp path.",
        })  # fmt: skip
        studio.api("PUT", f"projects/{pid}/plan", json={
            "compute": "customer", "memory_gb": 2, "timeout_seconds": 60, "log_retention_days": 7,
        })  # fmt: skip
        selection = {
            "model": args.model, "accelerator": args.accelerator, "threads": args.threads,
            "memory_mb": args.memory_mb, "context_tokens": 4096, "request_timeout_seconds": 60,
            "max_tokens": 256, "evaluation_budget_seconds": 900,
        }  # fmt: skip
        step = steps["select"] = {}
        check(studio.api("PUT", f"projects/{pid}/managed", json=selection).status_code == 200,
              "selection saved", step)  # fmt: skip

        # Prepare (optionally interrupt a fresh download, then resume it).
        step = steps["prepare"] = {"fresh_download": args.fresh_download}
        began = time.monotonic()
        studio.api("POST", f"projects/{pid}/managed/prepare", json={"consent": True})
        if args.fresh_download:
            while True:
                view = studio.api("GET", f"projects/{pid}/managed").json()
                job = view.get("preparation") or {}
                if job.get("phase") == "weights" and job.get("bytes", 0) > recipe.weights.size // 4:
                    break
                time.sleep(0.5)
            studio.api("POST", f"projects/{pid}/managed/cancel")
            view = wait_status(studio, pid, {"failed"}, 120)
            partial = (view.get("weights") or {}).get("bytes", 0)
            step["interrupted_at_bytes"] = partial
            check(view.get("reason") == "download_cancelled", "interrupted download recorded", step)
            check(0 < partial < recipe.weights.size, "partial bytes kept for resume", step)
            check(not (artifacts / "blobs" / "sha256" / recipe.weights.sha256).exists(),
                  "partial weights never published", step)  # fmt: skip
            studio.api("POST", f"projects/{pid}/managed/prepare", json={"consent": True})
        view = wait_status(studio, pid, {"prepared", "failed"})
        step["seconds"] = round(time.monotonic() - began, 1)
        check(view.get("status") == "prepared", "images pulled and weights verified", step)
        step["manifest_sha256"] = view.get("manifest_sha256")

        suite = studio.api("POST", f"projects/{pid}/managed/suite").json()
        steps["suite"] = {"cases": len(suite["cases"])}

        # Start, readiness and automatic connection.
        step = steps["start"] = {}
        gpu_before = gpu_memory_mib()
        began = time.monotonic()
        started = studio.api("POST", f"projects/{pid}/managed/start", json={"consent": True})
        step["seconds"] = round(time.monotonic() - began, 2)
        gpu_after = gpu_memory_mib()
        step["host_gpu_memory_mib"] = {"before_start": gpu_before, "after_ready": gpu_after}
        view = started.json()
        check(started.status_code == 200 and view.get("status") == "ready", "server ready", step)
        step.update(start_seconds=view.get("start_seconds"), load_seconds=view.get("load_seconds"))
        endpoint = studio.api("GET", f"projects/{pid}/model").json()["model_endpoint"]
        check(endpoint["state"]["status"] == "connected", "connected automatically", step)
        names = model_container(scope)
        model_name = next(n for n in names if n.startswith("furnace-model-"))
        inspected = json.loads(run("docker", "inspect", model_name))[0]
        env = dict(e.split("=", 1) for e in inspected["Config"]["Env"] if "=" in e)
        key = env.get("LLAMA_API_KEY", "")
        host = inspected["HostConfig"]
        step["isolation"] = {
            "user": inspected["Config"]["User"], "read_only_root": host["ReadonlyRootfs"],
            "cap_drop": host["CapDrop"], "memory_bytes": host["Memory"],
            "networks": list(inspected["NetworkSettings"]["Networks"]),
            "gpus_requested": bool(host.get("DeviceRequests")),
        }  # fmt: skip
        check(host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"], "container hardened", step)
        check(len(key) >= 32, "per-launch key generated", step)
        port = int(re.search(r":(\d+)/v1", view["launch"]["base_url"]).group(1))  # type: ignore[union-attr]
        unauthenticated = httpx.post(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            json={"model": recipe.alias, "messages": [{"role": "user", "content": "hi"}]},
            timeout=30, trust_env=False,
        )  # fmt: skip
        check(unauthenticated.status_code == 401, "server refuses requests without the key", step)
        egress = subprocess.run(  # noqa: S603
            ["docker", "run", "--rm", "--network", step["isolation"]["networks"][0],  # noqa: S607
             "alpine/socat@sha256:7f9a06753033f2b7de18edc2353f2c15153413d95a039163c6db270fc7a6c3b0",
             "-T3", "-", "TCP:1.1.1.1:443,connect-timeout=3"],
            input="", capture_output=True, text=True, timeout=60, check=False,
        )  # fmt: skip
        check(egress.returncode != 0, "model network has no internet route", step)

        # Inference.
        step = steps["inference"] = {}
        reply = studio.api("POST", f"projects/{pid}/model/predict",
                           json={"input": "What is 17 + 25? Reply with only the number."}).json()  # fmt: skip
        step.update(output=reply.get("output"), finish=reply.get("finish_reason"),
                    duration_ms=reply.get("duration_ms"), usage=reply.get("usage"),
                    server_timings=reply.get("server_timings"))  # fmt: skip
        check(bool(reply.get("output")), "real completion returned", step)

        # Reference-suite evaluation twice: rule checks and reproducibility.
        runs = []
        for attempt in (1, 2):
            step = steps[f"evaluation_{attempt}"] = {}
            result = studio.api("POST", f"projects/{pid}/model/evaluate").json()["model_endpoint"]
            run_record = result["evaluation"]
            runs.append(run_record)
            statuses = [r["status"] for r in run_record["results"]]
            step.update(
                status=run_record["status"], elapsed_seconds=run_record.get("elapsed_seconds"),
                passed=statuses.count("check_pass") + statuses.count("exact_pass"),
                failed=statuses.count("check_fail") + statuses.count("exact_fail"),
                incomplete=statuses.count("incomplete"), errors=statuses.count("error"),
                per_case=[{k: r.get(k) for k in ("status", "scoring_method", "reason", "duration_ms", "usage", "server_timings")} for r in run_record["results"]],
                reproducibility=result.get("reproducibility"),
            )  # fmt: skip
            check(run_record["status"] == "completed" and len(statuses) == len(suite["cases"]),
                  f"evaluation {attempt} completed every case", step)  # fmt: skip
        check(steps["evaluation_2"]["reproducibility"]["status"] == "identical",
              "second run reproduced every output", steps["evaluation_2"])  # fmt: skip

        # Record actual outputs once for reviewers by re-executing each case ad hoc,
        # and confirm they hash identically to the evaluated outputs.
        import hashlib

        outputs, matched = [], 0
        for index, case in enumerate(suite["cases"]):
            out = studio.api(
                "POST", f"projects/{pid}/model/predict", json={"input": case["input"]}
            ).json()
            text = out.get("output", "")
            same = (
                hashlib.sha256(text.encode()).hexdigest()
                == runs[1]["results"][index]["output_sha256"]
            )
            matched += same
            outputs.append(
                {"case": case["name"], "output": text[:300], "matches_evaluated_hash": same}
            )
        steps["outputs"] = {"cases": outputs, "identical_to_evaluation": matched}

        # Observability and privacy of logs.
        step = steps["observe"] = {}
        observed = studio.api("GET", f"projects/{pid}/managed/observe").json()
        logs = observed.get("logs", "")
        step.update(resources=observed.get("resources"),
                    metrics={k: v for k, v in observed.get("metrics", {}).items() if "total" in k or "processing" in k},
                    operations=len(observed.get("operations", [])))  # fmt: skip
        check(bool(observed.get("metrics")), "server metrics collected", step)
        check(suite["cases"][0]["input"] not in logs, "server log omits prompt text", step)
        check(key not in logs, "server log omits the key", step)
        # b12004 no longer logs per-layer offload at default verbosity, so GPU use is
        # measured directly: host GPU memory must grow by at least half the weights.
        memory = steps["start"]["host_gpu_memory_mib"]
        if None not in memory.values():
            step["gpu_memory_growth_mib"] = memory["after_ready"] - memory["before_start"]
        if args.accelerator == "nvidia":
            threshold = recipe.weights.size / 2**20 / 2
            check(step.get("gpu_memory_growth_mib", 0) >= threshold,
                  "model weights resident in GPU memory", step)  # fmt: skip

        # Failure: kill the server container while an evaluation is running.
        step = steps["crash_during_evaluation"] = {}
        holder: dict[str, Any] = {}
        worker = threading.Thread(
            target=lambda: holder.update(
                r=studio.api("POST", f"projects/{pid}/model/evaluate").json()
            )
        )
        worker.start()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            current = studio.api("GET", f"projects/{pid}/model").json()["model_endpoint"][
                "evaluation"
            ]
            if (
                current
                and current.get("status") == "running"
                and len(current.get("results", [])) >= 2
            ):
                break
            time.sleep(0.05)
        run("docker", "kill", model_name)
        worker.join(timeout=180)
        interrupted = holder["r"]["model_endpoint"]["evaluation"]
        step.update(status=interrupted["status"], recorded=len(interrupted["results"]),
                    last=interrupted["results"][-1])  # fmt: skip
        check(interrupted["status"] == "interrupted" and interrupted["results"][-1]["status"] == "error",
              "crash interrupts the run with an error, never a pass", step)  # fmt: skip
        failed = studio.api("GET", f"projects/{pid}/managed").json()
        step["managed_status"], step["reason"] = failed.get("status"), failed.get("reason")
        check(failed.get("status") == "failed" and str(failed.get("reason", "")).startswith("server_exited"),
              "server exit detected and recorded", step)  # fmt: skip
        check(studio.api("POST", f"projects/{pid}/model/evaluate").status_code == 409,
              "no hidden retry after the crash", step)  # fmt: skip
        check(model_container(scope) == [], "crashed server cleaned up", step)

        # Explicit restart and reproducibility across launches.
        step = steps["restart"] = {}
        began = time.monotonic()
        restarted = studio.api("POST", f"projects/{pid}/managed/start", json={"consent": True})
        step["seconds"] = round(time.monotonic() - began, 2)
        check(restarted.status_code == 200, "explicit restart ready", step)
        result = studio.api("POST", f"projects/{pid}/model/evaluate").json()["model_endpoint"]
        step["reproducibility"] = result.get("reproducibility")
        check(
            result["evaluation"]["status"] == "completed",
            "evaluation after restart completed",
            step,
        )
        check((result.get("reproducibility") or {}).get("status") == "identical",
              "outputs identical across server launches", step)  # fmt: skip

        # Hard Studio crash while the server runs; recovery on reopen.
        step = steps["studio_crash"] = {}
        studio.kill_hard()
        left = model_container(scope)
        step["containers_after_crash"] = len(left)
        check(len(left) == 2, "Docker-owned server outlives the crashed Studio", step)
        steps["studio_reopen"] = {"seconds": studio.start()}
        view = studio.api("GET", f"projects/{pid}/managed").json()
        step["status_after_reopen"] = view.get("status")
        check(view.get("status") == "interrupted", "reopen marks the launch interrupted", step)
        check(model_container(scope) == [], "reopen removed the orphaned containers", step)
        endpoint = studio.api("GET", f"projects/{pid}/model").json()["model_endpoint"]
        check(
            endpoint["state"]["status"] == "disconnected", "reopen never reconnects by itself", step
        )
        check(studio.api("POST", f"projects/{pid}/managed/start", json={"consent": True}).status_code == 200,
              "start after reopen ready", step)  # fmt: skip

        # Export.
        step = steps["export"] = {}
        archive = zipfile.ZipFile(io.BytesIO(studio.api("POST", f"projects/{pid}/kit").content))
        names = archive.namelist()
        plan = json.loads(archive.read("workspace-plan.json"))
        manifest = json.loads(archive.read("serving-manifest.json"))
        from furnace.runtime.catalog import manifest_digest

        blob = b"".join(archive.read(n) for n in names)
        new_key = dict(
            e.split("=", 1)
            for e in json.loads(run("docker", "inspect", next(n for n in model_container(scope) if n.startswith("furnace-model-"))))[0]["Config"]["Env"]
            if "=" in e
        ).get("LLAMA_API_KEY", "")  # fmt: skip
        step.update(files=sorted(names), history=len(plan["model_endpoint"]["history"]),
                    operations=len(plan["operations"]))  # fmt: skip
        check(manifest_digest(manifest) == plan["managed_server"]["manifest_sha256"],
              "exported manifest matches its recorded digest", step)  # fmt: skip
        check(key.encode() not in blob and new_key.encode() not in blob, "export omits keys", step)
        db = (workspace / "studio.sqlite3").read_bytes()
        oplog = (workspace / "logs" / "operations.jsonl").read_text(encoding="utf-8")
        check(key.encode() not in db and new_key.encode() not in db, "database omits keys", step)
        check(key not in oplog and new_key not in oplog, "operations log omits keys", step)
        check(suite["cases"][0]["input"] not in oplog, "operations log omits prompts", step)

        # Stop.
        step = steps["stop"] = {}
        stopped = studio.api("POST", f"projects/{pid}/managed/stop").json()
        check(stopped.get("status") == "stopped" and model_container(scope) == [],
              "stop removed every container", step)  # fmt: skip
        studio.stop_gracefully()
    finally:
        with contextlib.suppress(Exception):
            if studio.process and studio.process.poll() is None:
                studio.kill_hard()
        for name in model_container(scope):
            run("docker", "rm", "-f", name)
        for name in run(
            "docker", "network", "ls", "--filter", scope, "--format", "{{.Name}}"
        ).split():
            run("docker", "network", "rm", name)
        record["failures"] = FAILURES
        record["result"] = "passed" if not FAILURES else "failed"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        shutil.rmtree(workspace, ignore_errors=True)
        if args.fresh_download:
            shutil.rmtree(artifacts, ignore_errors=True)
    print(f"Result: {record['result']} ({len(FAILURES)} failed checks) -> {args.out}", flush=True)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
