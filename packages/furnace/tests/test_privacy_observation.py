"""Receipt observations must reflect Docker responses and exclude launch secrets."""

import json
import subprocess

import pytest
from furnace.runtime.serving import Supervisor


@pytest.mark.parametrize("unsafe", [None, "network", "root", "ports"])
def test_privacy_observation_uses_actual_configuration(tmp_path, monkeypatch, unsafe):
    supervisor = Supervisor(tmp_path, lambda: {})
    pid = "a" * 32
    names = supervisor.names(pid)
    state = {
        "running": True,
        "launch_id": "launch",
        "container_id": "container",
        "networks": [names["network"]],
    }
    info = {
        "Config": {
            "Image": "example@sha256:" + "b" * 64,
            "User": "10001:10001",
            "Env": ["LLAMA_API_KEY=private-launch-key"],
        },
        "HostConfig": {
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "PortBindings": {},
        },
        "Mounts": [{"Type": "bind", "RW": False}],
    }
    network = {"Internal": unsafe != "network"}
    if unsafe == "root":
        info["Config"]["User"] = "0"
    if unsafe == "ports":
        info["HostConfig"]["PortBindings"] = {"8080/tcp": [{"HostIp": "0.0.0.0"}]}
    monkeypatch.setattr(supervisor, "container_state", lambda _: state)

    def docker(*args, **kwargs):
        payload = network if args[0] == "network" else info
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr(supervisor, "_docker", docker)
    result = supervisor.privacy_state(pid)
    assert result["evidence_kind"] == "docker_inspect"
    assert all(result["checks"].values()) is (unsafe is None)
    assert "private-launch-key" not in json.dumps(result)
