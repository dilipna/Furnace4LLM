"""Four-condition experiment; reuse FurnaceBench without changing its timing code."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from furnace_bench.report.writer import write_result
from furnace_bench.runner import run_benchmark
from furnace_bench.schema import AdapterName, BenchPlan, BenchTarget, LengthMode, PromptMode
from furnace_bench.telemetry.prom import parse_prometheus
from furnace_bench.workload_spec import WorkloadSource, WorkloadSpec

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
IMAGE = "vllm/vllm-openai@sha256:8a69ffad015f138d7170c4ddc429e230a3bc1c1719f67e14324749df200a4b90"
CONDITIONS = {
    "A": "stable / cache on",
    "B": "stable / cache off",
    "C": "metadata first / cache on",
    "D": "metadata last / cache on",
}
COMMON_FLAGS = [
    "--model",
    MODEL,
    "--revision",
    REVISION,
    "--served-model-name",
    "lab",
    "--gpu-memory-utilization",
    "0.70",
    "--max-model-len",
    "4096",
    "--max-num-seqs",
    "8",
    "--block-size",
    "16",
    "--seed",
    "7",
]
TOPICS = [
    "an error spike",
    "a slow first token",
    "a growing queue",
    "exhausted database connections",
    "a failed rollout",
    "a missing approval",
    "an upstream timeout",
    "a regional outage",
    "missing cache metrics",
    "an unhealthy replica",
    "a retry storm",
    "an out-of-memory error",
]
ASKS = [
    "What should I check first?",
    "What evidence would distinguish likely causes?",
    "Which reversible action is appropriate?",
    "What should the incident update include?",
    "How should I verify recovery?",
]


def sh(*args: str, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed executables/argv, no shell evaluation
        list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=check,
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def redact(text: str) -> str:
    text = text.replace(str(ROOT), "<repository>").replace(str(Path.home()), "<home>")
    return re.sub(r"/(?:root|usr|opt|tmp|workspace|app)/[^\s'\"\],;)]*", "<container-path>", text)


def tokenize(base: str, text: str) -> int:
    response = httpx.post(
        f"{base}/tokenize",
        json={"model": "lab", "prompt": text, "add_special_tokens": False},
        timeout=20,
    )
    response.raise_for_status()
    return int(response.json()["count"])


def make_prefix(base: str) -> tuple[str, int]:
    words = (HERE / "runbook.txt").read_text(encoding="utf-8").split()
    low, high = 1, len(words)
    while low < high:
        mid = (low + high + 1) // 2
        if tokenize(base, " ".join(words[:mid])) <= 1500:
            low = mid
        else:
            high = mid - 1
    prefix = " ".join(words[:low])
    count = tokenize(base, prefix)
    if not 1450 <= count <= 1500:
        raise RuntimeError(f"runbook has {count} tokens; need 1450–1500")
    return prefix, count


def queries() -> list[str]:
    return [
        f"Ticket OPS-{i + 1:03}: Investigate {topic}. {ask}"
        for i, (topic, ask) in enumerate((t, a) for t in TOPICS for a in ASKS)
    ]


def system_message(condition: str, prefix: str, metadata: str) -> str:
    if condition == "C":
        return metadata + "\n\n" + prefix
    if condition == "D":
        return prefix + "\n\n" + metadata
    return prefix


def payloads(condition: str, prefix: str, qs: list[str], metadata: list[str]) -> list[dict]:
    return [
        {
            "messages": [
                {"role": "system", "content": system_message(condition, prefix, m)},
                {"role": "user", "content": q},
            ],
            "max_tokens": 32,
        }
        for q, m in zip(qs, metadata, strict=True)
    ]


def replay(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def snapshot(base: str) -> tuple[str, dict[str, float]]:
    response = httpx.get(f"{base}/metrics", timeout=15)
    response.raise_for_status()
    return response.text, parse_prometheus(response.text)


def cache_counts(metrics: dict[str, float]) -> tuple[float | None, float | None]:
    def get(stem):
        for key in (
            f"vllm:prefix_cache_{stem}_total",
            f"vllm:prefix_cache_{stem}",
            f"vllm:gpu_prefix_cache_{stem}_total",
        ):
            if key in metrics:
                return metrics[key]
        return None

    return get("hits"), get("queries")


def cache_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float | None]:
    bh, bq = cache_counts(before)
    ah, aq = cache_counts(after)
    if None in (bh, bq, ah, aq):
        return {"hits": None, "queries": None, "rate": None}
    hits, count = float(ah) - float(bh), float(aq) - float(bq)  # type: ignore[arg-type]
    if count < 0 or hits < 0 or hits > count:
        raise RuntimeError("invalid or reset cache counters")
    return {"hits": hits, "queries": count, "rate": hits / count if count else None}


def gpu() -> str:
    return sh(
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,memory.used,clocks.sm,power.draw,power.limit",
        "--format=csv,noheader,nounits",
    ).stdout.strip()


def on_ac() -> bool | None:
    if sys.platform == "win32":
        import ctypes

        class Power(ctypes.Structure):
            _fields_ = [
                ("ac", ctypes.c_ubyte),
                ("flags", ctypes.c_ubyte),
                ("percent", ctypes.c_ubyte),
                ("reserved", ctypes.c_ubyte),
                ("life", ctypes.c_ulong),
                ("full", ctypes.c_ulong),
            ]

        value = Power()
        return (
            bool(value.ac)
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(value)) and value.ac != 255
            else None
        )
    supplies = list(Path("/sys/class/power_supply").glob("*/online"))
    return any(p.read_text().strip() == "1" for p in supplies) if supplies else None


def wait_ready(name: str, base: str) -> None:
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base}/v1/models", timeout=3)
            if response.status_code == 200 and any(
                m["id"] == "lab" for m in response.json().get("data", [])
            ):
                return
        except httpx.HTTPError:
            pass
        state = sh(
            "docker", "inspect", name, "--format", "{{.State.Running}}", check=False
        ).stdout.strip()
        if state != "true":
            raise RuntimeError("server exited before readiness; see preserved server log")
        time.sleep(3)
    raise TimeoutError("server not ready after 600 seconds")


def measure(base: str, path: Path, n: int, label: str):
    target = BenchTarget(
        adapter=AdapterName.vllm,
        base_url=f"{base}/v1",
        model="lab",
        metrics_url=f"{base}/metrics",
        label=label,
        server_flags={"common": COMMON_FLAGS, "image": IMAGE, "cache": label[0] != "B"},
    )
    plan = BenchPlan(
        concurrency_levels=[1],
        requests_per_level=n,
        warmup_requests=0,
        cooldown_s=0,
        prompt_mode=PromptMode.replay,
        replay_path=path.relative_to(ROOT).as_posix(),
        length_mode=LengthMode.fixed,
        seed=7,
    )
    spec = WorkloadSpec(
        name="synthetic-ops-runbook", source=WorkloadSource.synthetic, synthetic=True, model=MODEL
    )
    result = asyncio.run(
        run_benchmark(
            target, spec, plan, sample_gpu=True, progress=lambda msg: print(msg, flush=True)
        )
    )
    return result


def require_complete(result: Any, n: int) -> None:
    if any(not r.ok for r in result.records) or len(result.records) != n:
        raise RuntimeError(f"incomplete request run: {sum(r.ok for r in result.records)}/{n}")


def run(args: argparse.Namespace) -> int:
    os.chdir(ROOT)
    out = HERE / "runs" / args.campaign
    out.mkdir(parents=True, exist_ok=False)
    if on_ac() is False:
        raise RuntimeError("laptop is on battery; connect AC before benchmarking")
    sh("docker", "version", "--format", "{{.Server.Version}}")
    sh("docker", "image", "inspect", IMAGE)
    cache = Path(
        os.environ.get("HF_HOME_HOST", str(Path.home() / ".cache" / "huggingface"))
    ).resolve()
    manifest = {
        "campaign": args.campaign,
        "started_utc": datetime.now(UTC).isoformat(),
        "model": MODEL,
        "model_revision": REVISION,
        "image": IMAGE,
        "flags": COMMON_FLAGS,
        "protocol_sha256": digest((HERE / "protocol.md").read_bytes()),
        "runbook_source_sha256": digest((HERE / "runbook.txt").read_bytes()),
        "driver_sha256": digest(Path(__file__).read_bytes()),
        "git_sha": sh("git", "rev-parse", "HEAD").stdout.strip(),
        "gpu_before": gpu(),
        "ac_before": on_ac(),
        "requests": 60,
        "warmup": 4,
        "repeats": 3,
        "order": ["ABCD", "BCDA", "CDAB"],
        "attempts": [],
    }
    save(out / "manifest.json", manifest)
    prefix = None
    for repeat, order in enumerate(manifest["order"]):
        metadata = [
            f"session={uuid.uuid4()} timestamp={datetime.now(UTC).isoformat()}" for _ in range(60)
        ]
        for condition in order:
            successful = False
            for attempt in range(2):
                name = f"furnace-prefix-{uuid.uuid4().hex[:10]}"
                dest = out / f"r{repeat + 1}-{condition}-attempt{attempt + 1}"
                dest.mkdir()
                record: dict[str, Any] = {
                    "repeat": repeat + 1,
                    "condition": condition,
                    "attempt": attempt + 1,
                    "status": "running",
                    "path": dest.relative_to(HERE).as_posix(),
                    "started_utc": datetime.now(UTC).isoformat(),
                    "gpu_before": gpu(),
                    "ac_before": on_ac(),
                }
                error = None
                print(
                    f"Starting repeat {repeat + 1}, condition {condition}, attempt {attempt + 1}",
                    flush=True,
                )
                try:
                    if on_ac() is False:
                        raise RuntimeError("AC disconnected")
                    flag = (
                        "--no-enable-prefix-caching"
                        if condition == "B"
                        else "--enable-prefix-caching"
                    )
                    sh(
                        "docker",
                        "run",
                        "-d",
                        "--pull=never",
                        "--name",
                        name,
                        "--gpus",
                        "all",
                        "--ipc",
                        "host",
                        "-p",
                        f"127.0.0.1:{args.port}:8000",
                        "-e",
                        "HF_HUB_OFFLINE=1",
                        "-v",
                        f"{cache.as_posix()}:/root/.cache/huggingface:ro",
                        "-v",
                        "furnace-prefix-compile:/root/.cache/vllm",
                        IMAGE,
                        *COMMON_FLAGS,
                        flag,
                    )
                    base = f"http://127.0.0.1:{args.port}"
                    wait_ready(name, base)
                    if prefix is None:
                        prefix, count = make_prefix(base)
                        (out / "prefix.txt").write_text(prefix, encoding="utf-8")
                        manifest.update(prefix_tokens=count, prefix_sha256=digest(prefix.encode()))
                    warm_metadata = [
                        f"session={uuid.uuid4()} timestamp={datetime.now(UTC).isoformat()}"
                        for _ in range(4)
                    ]
                    warm = dest / "warmup.jsonl"
                    replay(
                        warm,
                        payloads(
                            condition,
                            prefix,
                            [f"Warmup {i}: summarize safe incident triage." for i in range(4)],
                            warm_metadata,
                        ),
                    )
                    warm_result = measure(base, warm, 4, f"{condition}-warmup")
                    write_result(warm_result, dest / "warmup")
                    require_complete(warm_result, 4)
                    time.sleep(
                        11
                    )  # allow the server's asynchronous counters/log interval to settle
                    before_text, before = snapshot(base)
                    path = dest / "workload.jsonl"
                    replay(path, payloads(condition, prefix, queries(), metadata))
                    result = measure(base, path, 60, condition)
                    write_result(result, dest / "measured")
                    require_complete(result, 60)
                    if any(
                        r.token_count_source != "server_usage" or r.output_tokens is None  # noqa: S105
                        for r in result.records
                    ):
                        raise RuntimeError(
                            "throughput needs server usage, not chunk-count estimates"
                        )
                    time.sleep(11)
                    after_text, after = snapshot(base)
                    (dest / "metrics-before.prom").write_text(before_text, encoding="utf-8")
                    (dest / "metrics-after.prom").write_text(after_text, encoding="utf-8")
                    level = result.report.levels[0]
                    record.update(
                        status="success",
                        ttft_p50_ms=level.ttft_ms.p50,
                        ttft_p95_ms=level.ttft_ms.p95,
                        output_tok_s=level.output_tok_s,
                        completion_tokens=sum(r.output_tokens or 0 for r in result.records),
                        window_s=level.window_s,
                        cache=cache_delta(before, after),
                        n_ok=level.n_ok,
                    )
                    successful = True
                except Exception as exc:
                    error = exc
                    record.update(status="failed", error=redact(f"{type(exc).__name__}: {exc}"))
                finally:
                    logs = sh("docker", "logs", name, timeout=30, check=False)
                    log_text = redact(logs.stdout + logs.stderr)
                    (dest / "server.log").write_text(log_text, encoding="utf-8")
                    record["logged_cache_percentages"] = [
                        float(v)
                        for v in re.findall(
                            r"(?:[Pp]refix cache hit rate|[Pp]refix cache hit rate \(GPU\)):\s*([\d.]+)%",
                            log_text,
                        )
                    ]
                    record["gpu_after"] = gpu()
                    record["ac_after"] = on_ac()
                    if record["ac_after"] is False:
                        record.update(status="failed", error="AC disconnected; attempt invalidated")
                        successful = False
                    sh("docker", "stop", "-t", "15", name, timeout=45, check=False)
                    sh("docker", "rm", name, check=False)
                    save(dest / "summary.json", record)
                    manifest["attempts"].append(record)
                    save(out / "manifest.json", manifest)
                    print(json.dumps(record), flush=True)
                if successful:
                    break
                if attempt == 1:
                    print(f"Stopping after identical retry failed: {error}", flush=True)
                    return 1
            if not successful:
                return 1
    manifest.update(finished_utc=datetime.now(UTC).isoformat(), gpu_after=gpu(), ac_after=on_ac())
    save(out / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", default=datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ"))
    parser.add_argument("--port", type=int, default=8115)
    arguments = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", arguments.campaign):
        parser.error("campaign must contain letters, digits, underscores or hyphens")
    raise SystemExit(run(arguments))
