import time
import uuid

import pytest
from furnace.runtime.manager import RuntimeFault, RuntimeManager

pytestmark = pytest.mark.adversarial


@pytest.fixture
def worker(tmp_path):
    manager = RuntimeManager(tmp_path)
    manager.prepare()
    project_id = uuid.uuid4().hex
    yield manager, project_id
    manager.stop(project_id)


def test_real_worker_isolation_predictions_idempotence_and_restart(worker, monkeypatch):
    manager, pid = worker
    monkeypatch.setenv("FURNACE_STUDIO_TEST_SECRET", "must-not-enter-container")
    first = manager.start(pid)
    assert first["status"] == "ready" and first["model_execution"] is False
    info = manager.inspect(pid)
    assert info["HostConfig"]["ReadonlyRootfs"] is True
    assert info["HostConfig"]["NetworkMode"] == "none"
    assert info["HostConfig"]["CapDrop"] == ["ALL"]
    assert info["HostConfig"]["Memory"] == 256 * 1024 * 1024
    assert info["HostConfig"]["PidsLimit"] == 64
    assert info["Config"]["User"] == "10001:10001"
    assert all(m["RW"] is False and m["Destination"] == "/worker.py" for m in info["Mounts"])
    assert "FURNACE_STUDIO_TEST_SECRET" not in str(info["Config"]["Env"])
    assert not info["HostConfig"]["PortBindings"]
    assert manager.start(pid)["container_id"] == first["container_id"]
    one = manager.predict(pid, "first input")
    two = manager.predict(pid, "second input")
    assert one["output"] == "framework:FIRST INPUT"
    assert two["output"] == "framework:SECOND INPUT"
    assert one["request_id"] != two["request_id"]
    assert one["duration_ms"] >= 0 and one["model_execution"] is False
    manager.stop(pid)
    assert manager.inspect(pid) is None
    second = manager.start(pid)
    assert second["container_id"] != first["container_id"]


@pytest.mark.parametrize(
    "operation,code",
    [("error", "worker_error"), ("crash", "docker_operation_failed"), ("timeout", "timeout")],
)
def test_real_worker_failure_stops_execution_and_can_restart(worker, operation, code):
    manager, pid = worker
    manager.start(pid)
    began = time.monotonic()
    with pytest.raises(RuntimeFault) as error:
        manager.predict(
            pid,
            "private input never logged",
            operation=operation,
            timeout_s=0.5 if operation == "timeout" else 5,
        )
    assert error.value.code == code
    assert time.monotonic() - began < 20
    assert manager.inspect(pid) is None
    assert manager.start(pid)["status"] == "ready"
    assert manager.predict(pid, "recovered")["output"] == "framework:RECOVERED"


def test_foreign_container_is_never_deleted_or_overwritten(worker):
    manager, pid = worker
    manager._docker(
        "run",
        "--detach",
        "--name",
        manager.name(pid),
        "--network",
        "none",
        "furnace-sandbox-py:0.1",
        "python",
        "-c",
        "import time; time.sleep(60)",
    )
    try:
        with pytest.raises(RuntimeFault, match="ownership_mismatch"):
            manager.start(pid)
        with pytest.raises(RuntimeFault, match="ownership_mismatch"):
            manager.stop(pid)
        result = manager._docker("inspect", manager.name(pid))
        assert result.returncode == 0
    finally:
        # The test itself owns this deliberately mismatched fixture container.
        manager._docker("rm", "--force", manager.name(pid))


def test_missing_daemon_is_not_reported_as_absent_worker(tmp_path, monkeypatch):
    manager = RuntimeManager(tmp_path)
    monkeypatch.setattr(
        manager,
        "_docker",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeFault("docker_unavailable")),
    )
    with pytest.raises(RuntimeFault, match="docker_unavailable"):
        manager.inspect(uuid.uuid4().hex)


def test_project_identifiers_cannot_inject_docker_arguments(tmp_path):
    manager = RuntimeManager(tmp_path)
    with pytest.raises(RuntimeFault, match="invalid_project"):
        manager.start("--privileged")


def test_remote_docker_is_refused_before_any_resource_operation(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "ssh://remote.example")
    manager = RuntimeManager(tmp_path)
    with pytest.raises(RuntimeFault, match="remote_docker_refused"):
        manager.prepare()


def test_local_endpoint_is_pinned_for_application_lifetime(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/local-test.sock")
    monkeypatch.setenv("DOCKER_CONTEXT", "remote-context")
    manager = RuntimeManager(tmp_path)
    first = manager.docker_environment()
    assert first["DOCKER_HOST"] == "unix:///tmp/local-test.sock"
    assert "DOCKER_CONTEXT" not in first
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2375")
    assert manager.docker_environment()["DOCKER_HOST"] == first["DOCKER_HOST"]
