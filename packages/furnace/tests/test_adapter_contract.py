"""Adapter contract, researcher host protocol and operations log; real loopback HTTP."""

import contextlib
import importlib
import json
import sys
import threading
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from furnace.runtime import pyserve
from furnace.runtime.adapter import LaunchSettings, LlamaCppAdapter, PythonAdapter
from furnace.runtime.catalog import MODELS
from furnace.runtime.endpoint import LocalChatEndpoint
from furnace.runtime.manager import RuntimeFault
from furnace.runtime.oplog import OperationsLog

FIXTURE = Path(__file__).with_name("adapter_fixture")
IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


@contextlib.contextmanager
def hosted(factory: str, key: str | None = "test-key-not-secret", max_tokens: int = 64):
    sys.path.insert(0, str(FIXTURE))
    try:
        adapter = getattr(importlib.import_module("toy_adapter"), factory)()
        host = pyserve.Host(adapter, "toy", max_tokens, key)
        server = ThreadingHTTPServer(("127.0.0.1", 0), pyserve.handler(host))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host.load(None)
        config = {
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "model_id": "toy",
            "timeout_seconds": 5,
            "max_tokens": 48,
        }
        try:
            yield host, config
        finally:
            server.shutdown()
            server.server_close()
    finally:
        sys.path.remove(str(FIXTURE))


def test_llama_cpp_launch_is_bounded_offline_and_keyed_by_environment():
    recipe = MODELS["qwen2.5-0.5b-instruct-q8_0"]
    adapter = LlamaCppAdapter(recipe)
    cpu = adapter.launch({recipe.weights.sha256: Path(__file__)}, LaunchSettings())
    flags = dict(zip(cpu.command[::2], cpu.command[1::2], strict=False))
    assert flags["--n-gpu-layers"] == "0" and flags["--parallel"] == "1"
    assert flags["--alias"] == recipe.alias and cpu.model_id == recipe.alias
    assert "--offline" in cpu.command and "--metrics" in cpu.command
    assert "--api-key" not in cpu.command  # the key travels in the environment only
    assert cpu.secret_env == "LLAMA_API_KEY" and not cpu.gpu
    assert [m.target for m in cpu.mounts] == ["/models/model.gguf"]
    gpu = adapter.launch(
        {recipe.weights.sha256: Path(__file__)}, LaunchSettings(accelerator="nvidia")
    )
    assert gpu.gpu and "999" in gpu.command and gpu.image != cpu.image
    assert adapter.images(LaunchSettings())[0].endswith(cpu.image.split("@")[1])


def test_python_adapter_requires_pinned_image_and_simple_entrypoint(tmp_path):
    with pytest.raises(ValueError, match="digest"):
        PythonAdapter("python:3.12-slim", tmp_path, "toy_adapter:Reverser", "toy")
    with pytest.raises(ValueError, match="entrypoint"):
        PythonAdapter(IMAGE, tmp_path, "toy_adapter:Reverser; rm -rf /", "toy")
    spec = PythonAdapter(IMAGE, FIXTURE, "toy_adapter:Reverser", "toy").launch({}, LaunchSettings())
    assert spec.entrypoint == "python" and spec.command[:2] == ("-I", "/furnace/pyserve.py")
    assert {m.target for m in spec.mounts} == {"/furnace/pyserve.py", "/adapter"}


def test_researcher_host_speaks_the_protocol_used_by_studio():
    client = LocalChatEndpoint()
    with hosted("Reverser") as (host, config):
        client.check(config, api_key="test-key-not-secret")
        result = client.predict(config, "abc", 5, api_key="test-key-not-secret")
        assert result["output"] == "reversed:cba state=1"
        assert result["finish_reason"] == "stop"
        # reset() runs before every request: no state leaks between users.
        again = client.predict(config, "xyz", 5, api_key="test-key-not-secret")
        assert again["output"].endswith("state=1")
        with pytest.raises(RuntimeFault, match="endpoint_http_401"):
            client.predict(config, "abc", 5)
        with pytest.raises(RuntimeFault, match="endpoint_http_401"):
            client.predict(config, "abc", 5, api_key="wrong")
        truncated = client.predict(
            {**config, "max_tokens": 5}, "abcdef", 5, api_key="test-key-not-secret"
        )
        assert truncated["finish_reason"] == "length"
        with pytest.raises(RuntimeFault, match="endpoint_http_500") as failure:
            client.predict(config, "fail", 5, api_key="test-key-not-secret")
        assert "PRIVATE" not in str(failure.value)
        assert host.counters["requests_total"] == 4 and host.counters["errors_total"] == 1


def test_researcher_host_reports_failed_load_and_rejects_invalid_requests():
    client = LocalChatEndpoint()
    with hosted("Broken") as (host, config):
        assert host.state == "failed"
        with pytest.raises(RuntimeFault, match="endpoint_http_503"):
            client.predict(config, "abc", 5, api_key="test-key-not-secret")
    with hosted("Reverser") as (_, config):
        with pytest.raises(RuntimeFault, match="endpoint_http_400"):
            client.predict({**config, "max_tokens": 65}, "abc", 5, api_key="test-key-not-secret")
        with pytest.raises(RuntimeFault, match="endpoint_http_400"):
            client.predict({**config, "model_id": "other"}, "abc", 5, api_key="test-key-not-secret")


def test_operations_log_refuses_content_rotates_and_prunes_by_retention(tmp_path, monkeypatch):
    log = OperationsLog(tmp_path)
    for field in ("input", "output", "prompt", "api_key"):
        with pytest.raises(ValueError, match="refuses"):
            log.append("p", "request", **{field: "x"})
    log.append("p", "request", request_id="r1", duration_ms=3)
    log.append("q", "request", request_id="r2")
    assert [e["request_id"] for e in log.read("p")] == ["r1"]
    monkeypatch.setattr("furnace.runtime.oplog.ROTATE_BYTES", 200)
    for index in range(20):
        log.append("p", "request", request_id=f"x{index}")
    assert 1 < len(log.files()) <= 5
    old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": old, "project_id": "p", "kind": "request"}) + "\n")
        handle.write("not json\n")
    removed = log.prune({"p": 7})
    assert removed == 2
    assert all(e["at"] != old for e in log.read("p", 1000))
