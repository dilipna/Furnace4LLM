"""Supervisor against real Docker with the Python adapter host. Requires local Docker.

The served adapter is the deterministic test reverser, not a model; these tests check
isolation, readiness, credentials, failure detection and recovery of real containers.
"""

import json
import subprocess
from pathlib import Path

import pytest
from furnace.runtime.adapter import LaunchSettings, PythonAdapter
from furnace.runtime.endpoint import LocalChatEndpoint
from furnace.runtime.manager import RuntimeFault, RuntimeManager
from furnace.runtime.serving import ServingFault, Supervisor

FIXTURE = Path(__file__).with_name("adapter_fixture")
IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"
PID = "a" * 32


def docker(*args, check=True):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


@pytest.fixture
def supervisor(tmp_path):
    manager = RuntimeManager(tmp_path)
    sup = Supervisor(tmp_path, manager.docker_environment)
    adapter = PythonAdapter(IMAGE, FIXTURE, "toy_adapter:Reverser", "toy", load_timeout_s=60)
    settings = LaunchSettings(memory_mb=256, cpus=1.0, max_output_tokens=64)
    for image in adapter.images(settings):
        sup.pull(image, timeout=600)
    try:
        yield sup, adapter, settings
    finally:
        sup.recover()


def inspect(name):
    return json.loads(docker("inspect", name).stdout)[0]


def test_managed_server_is_isolated_keyed_observable_and_recoverable(supervisor):
    sup, adapter, settings = supervisor
    spec = adapter.launch({}, settings)
    launch = sup.start(PID, spec, {"furnace.managed.manifest": "test"})
    sup.wait_ready(PID, spec)
    names = sup.names(PID)
    model, relay = inspect(names["model"]), inspect(names["relay"])
    host = model["HostConfig"]
    assert host["ReadonlyRootfs"] is True and host["CapDrop"] == ["ALL"]
    assert "no-new-privileges" in host["SecurityOpt"] and model["Config"]["User"] == "10001:10001"
    assert host["Memory"] == 256 * 1024 * 1024 and host["MemorySwap"] == host["Memory"]
    assert host["PortBindings"] in ({}, None)  # only the relay is published
    assert list(model["NetworkSettings"]["Networks"]) == [names["network"]]
    assert all(m["RW"] is False for m in model["Mounts"])
    assert json.loads(docker("network", "inspect", names["network"]).stdout)[0]["Internal"]
    bindings = relay["HostConfig"]["PortBindings"]["8080/tcp"]
    assert [b["HostIp"] for b in bindings] == ["127.0.0.1"]
    key = sup.api_key(PID)
    assert key and key not in json.dumps(model["Config"]["Cmd"])
    egress = docker(
        "exec", names["model"], "python", "-c",
        "import socket; socket.create_connection(('1.1.1.1', 443), timeout=3)",
        check=False,
    )  # fmt: skip
    assert egress.returncode != 0  # no route out of the internal network

    client = LocalChatEndpoint()
    config = {
        "base_url": launch["base_url"],
        "model_id": "toy",
        "timeout_seconds": 10,
        "max_tokens": 48,
    }
    assert client.predict(config, "abc", 10, api_key=key)["output"] == "reversed:cba state=1"
    with pytest.raises(RuntimeFault, match="endpoint_http_401"):
        client.predict(config, "abc", 10)
    # The unauthenticated request was refused before reaching the adapter.
    assert sup.metrics(PID)["furnace_adapter:requests_total"] == 1.0
    assert "abc" not in sup.logs(PID) and key not in sup.logs(PID)
    assert sup.stats(PID).get("memory")

    docker("kill", names["model"])
    state = sup.container_state(PID)
    assert state["running"] is False and state["failure"] == "server_exited_137"

    removed = sup.recover()
    assert set(removed) == set(names.values())
    label = f"label=furnace.managed.workspace={sup.scope}"
    assert docker("ps", "-a", "--filter", label, "-q").stdout.strip() == ""
    assert docker("network", "ls", "--filter", label, "-q").stdout.strip() == ""
    assert sup.api_key(PID) is None


def test_failed_load_is_reported_and_cleanup_refuses_foreign_containers(supervisor, tmp_path):
    sup, _, settings = supervisor
    broken = PythonAdapter(IMAGE, FIXTURE, "toy_adapter:Broken", "toy", load_timeout_s=30)
    spec = broken.launch({}, settings)
    sup.start(PID, spec, {})
    with pytest.raises(ServingFault, match="server_load_failed"):
        sup.wait_ready(PID, spec)
    sup.stop(PID)
    assert sup.container_state(PID)["present"] is False

    other = Supervisor(tmp_path / "another-workspace", RuntimeManager(tmp_path).docker_environment)
    sup.start(PID, broken.launch({}, settings), {})
    # Same project id, different workspace scope: names differ, so nothing is shared...
    assert other.names(PID)["model"] != sup.names(PID)["model"]
    # ...and a container carrying another scope's labels under our name is never removed.
    name = sup.names(PID)["model"]
    docker("rm", "-f", name)
    docker("run", "-d", "--name", name, "--label", "furnace.managed.workspace=foreign",
           "--label", f"furnace.managed.project={PID}", IMAGE, "sleep", "60")  # fmt: skip
    try:
        with pytest.raises(ServingFault, match="ownership_mismatch"):
            sup.stop(PID)
    finally:
        docker("rm", "-f", name, check=False)


def test_cleanup_dry_run_then_removes_only_this_workspace(supervisor, tmp_path):
    from furnace.runtime.cleanup import cleanup
    from furnace.runtime.lease import WorkspaceBusy, WorkspaceLease

    sup, adapter, settings = supervisor
    sup.start(PID, adapter.launch({}, settings), {})
    store = tmp_path / "artifacts"
    (store / "blobs" / "sha256").mkdir(parents=True)
    blob = store / "blobs" / "sha256" / ("b" * 64)
    blob.write_bytes(b"weights")
    blob.chmod(0o444)
    (store / "keep-me.txt").write_text("not part of the store", encoding="utf-8")
    other = tmp_path / "other-workspace"
    other_sup = Supervisor(other, RuntimeManager(other).docker_environment)
    other_sup.start(PID, adapter.launch({}, settings), {})
    try:
        with WorkspaceLease(tmp_path), pytest.raises(WorkspaceBusy):
            cleanup(tmp_path, store)
        planned = cleanup(tmp_path, store, dry_run=True)
        assert len(planned["containers"]) == 2 and len(planned["networks"]) == 1
        assert sup.container_state(PID)["running"] and blob.exists()
        done = cleanup(tmp_path, store, dry_run=False)
        assert done["artifacts"]["bytes"] == len(b"weights")
        assert sup.container_state(PID)["present"] is False
        assert not (store / "blobs").exists() and (store / "keep-me.txt").exists()
        assert other_sup.container_state(PID)["running"]  # another workspace is untouched
    finally:
        other_sup.recover()
