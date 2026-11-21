"""Managed-server orchestration in Studio over real loopback HTTP.

The supervisor double hosts the real researcher protocol server (pyserve) in-process
with a scripted test adapter instead of a Docker container: no model, weights or
Docker are involved. Real-model validation is recorded separately.
"""

import io
import threading
import time
import uuid
import zipfile
from http.server import ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from furnace.runtime import pyserve
from furnace.runtime.artifacts import ArtifactError
from furnace.runtime.lease import WorkspaceBusy, WorkspaceLease
from furnace.runtime.serving import ServingFault
from furnace_api.studio import create_app

TOKEN = "managed-server-orchestration-test-session-" * 2
MODEL = "qwen2.5-0.5b-instruct-q8_0"
ANSWERS = {
    "17 + 25": "42",
    "capital of France": "Paris.",
    "Red Planet": "B",
    "backwards": "desserts",
}


class Scripted:
    """Answers a few suite questions deterministically; not a model."""

    def __init__(self, on_crash):
        self.on_crash = on_crash

    def load(self, weights_dir):
        pass

    def generate(self, messages, max_tokens, temperature):
        text = messages[-1]["content"]
        if "CRASH" in text:
            self.on_crash()
            raise RuntimeError("server died")
        for needle, answer in ANSWERS.items():
            if needle in text:
                return answer, "stop"
        return "I am not sure.", "stop"


class FakeSupervisor:
    def __init__(self):
        self.servers, self.keys, self.ports, self.alive = {}, {}, {}, {}
        self.fail_ready: str | None = None
        self.started = 0

    def daemon(self):
        return {"status": "ready", "gpu_runtime": False}

    def image_present(self, image):
        return True

    def pull(self, image, timeout=1800, cancel=None):
        pass

    def start(self, pid, spec, labels):
        self.stop(pid)
        key = uuid.uuid4().hex + uuid.uuid4().hex
        host = pyserve.Host(Scripted(lambda: self.crash(pid)), spec.model_id, 1024, key)
        server = ThreadingHTTPServer(("127.0.0.1", 0), pyserve.handler(host))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        host.load(None)
        self.servers[pid], self.keys[pid] = server, key
        self.ports[pid], self.alive[pid] = server.server_port, True
        self.started += 1
        port = server.server_port
        return {
            "launch_id": uuid.uuid4().hex,
            "port": port,
            "base_url": f"http://127.0.0.1:{port}/v1",
            "started_at": "now",
        }

    def wait_ready(self, pid, spec, cancel=None, on_state=None):
        if self.fail_ready:
            raise ServingFault(self.fail_ready, {"oom_killed": True})
        return {"load_seconds": 0.01}

    def crash(self, pid):
        self.alive[pid] = False

    def container_state(self, pid):
        if pid not in self.servers:
            return {"running": False, "present": False, "failure": "server_container_missing"}
        running = self.alive[pid]
        return {
            "running": running,
            "present": True,
            "failure": None if running else "server_exited_137",
            "exit_code": 0 if running else 137,
        }

    def stop(self, pid):
        server = self.servers.pop(pid, None)
        if server is not None:
            threading.Thread(target=server.shutdown, daemon=True).start()
            server.server_close()
        self.keys.pop(pid, None)
        self.ports.pop(pid, None)

    def recover(self):
        names = [f"furnace-model-{pid}" for pid in self.servers]
        for pid in list(self.servers):
            self.stop(pid)
        return names

    def api_key(self, pid):
        return self.keys.get(pid)

    def port(self, pid):
        return self.ports.get(pid)

    def logs(self, pid, tail=200):
        return "srv  load_model: loaded\n"

    def stats(self, pid):
        return {"memory": "10MiB / 2GiB"}

    def metrics(self, pid):
        return {"llamacpp:requests_processing": 0.0}


class FakeArtifacts:
    def __init__(self, tmp_path):
        self.file = tmp_path / "weights.bin"
        self.fetched = False
        self.block = threading.Event()
        self.block.set()

    def status(self, artifact):
        return {"state": "present" if self.fetched else "absent", "bytes": 0, "size": artifact.size}

    def fetch(self, artifact, progress=None, cancel=None):
        while not self.block.wait(0.01):
            if cancel is not None and cancel.is_set():
                raise ArtifactError("download_cancelled")
        if progress:
            progress(artifact.size, artifact.size)
        self.file.write_bytes(b"gguf")
        self.fetched = True
        return self.file

    def verify(self, artifact, cancel=None):
        if not self.fetched:
            raise ArtifactError("artifact_missing")
        return self.file


def build(tmp_path, fake=None, artifacts=None):
    app = create_app(tmp_path / "ws", TOKEN)
    fake = fake or FakeSupervisor()
    app.state.managed.supervisor = fake
    app.state.managed.artifacts = artifacts or FakeArtifacts(tmp_path)
    app.state.model.credentials = fake.api_key
    return app, fake


def client_for(app):
    return TestClient(app, base_url="http://localhost", headers={"x-furnace-session": TOKEN})


def wait_for(client, pid, status, timeout=5.0):
    deadline = time.monotonic() + timeout
    view = {}
    while time.monotonic() < deadline:
        view = client.get(f"/api/projects/{pid}/managed").json()
        if view["status"] == status:
            return view
        time.sleep(0.02)
    raise AssertionError(f"managed server never reached {status}: {view}")


def ready_project(client, cpu_settings=None):
    pid = client.post("/api/examples/framework").json()["id"]
    selection = {
        "model": MODEL,
        "accelerator": "cpu",
        "request_timeout_seconds": 5,
        **(cpu_settings or {}),
    }
    assert client.put(f"/api/projects/{pid}/managed", json=selection).status_code == 200
    assert (
        client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True}).status_code
        == 200
    )
    wait_for(client, pid, "prepared")
    assert client.post(f"/api/projects/{pid}/managed/suite").status_code == 200
    started = client.post(f"/api/projects/{pid}/managed/start", json={"consent": True})
    assert started.status_code == 200, started.text
    return pid


def test_full_managed_journey_scores_reproduces_and_exports_without_secrets(tmp_path):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        project = client.get(f"/api/projects/{pid}/model").json()
        assert project["managed_server"]["status"] == "ready"
        endpoint = project["model_endpoint"]
        assert endpoint["state"]["status"] == "connected"
        assert endpoint["server_managed_by_furnace"] and endpoint["weights_verified_before_launch"]
        assert (
            endpoint["connection"]["server"]["manifest_sha256"]
            == project["managed_server"]["manifest_sha256"]
        )
        assert len(project["cases"]) == 12

        reply = client.post(
            f"/api/projects/{pid}/model/predict", json={"input": "What is 17 + 25?"}
        )
        assert reply.json()["output"] == "42"
        first = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"]
        run = first["evaluation"]
        assert run["status"] == "completed" and len(run["results"]) == 12
        statuses = [r["status"] for r in run["results"]]
        assert statuses.count("check_pass") == 4 and statuses.count("check_fail") == 8
        assert {r["scoring_method"] for r in run["results"]} >= {"numeric", "choice", "json_fields"}
        assert run["suite_sha256"] and run["server"]["weights_sha256"]
        assert first["reproducibility"]["status"] == "no_earlier_run"
        second = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"]
        assert second["reproducibility"] == {
            **second["reproducibility"],
            "status": "identical",
            "compared": 12,
            "identical": 12,
        }

        observed = client.get(f"/api/projects/{pid}/managed/observe").json()
        assert observed["container"]["running"] and observed["metrics"]
        kinds = [e["kind"] for e in observed["operations"]]
        assert {"prepared", "ready", "connected", "request", "evaluation_ended"} <= set(kinds)

        key = fake.api_key(pid)
        assert key is not None
        archive = zipfile.ZipFile(io.BytesIO(client.post(f"/api/projects/{pid}/kit").content))
        names = set(archive.namelist())
        assert {"serving-manifest.json", "workspace-plan.json"} <= names
        blob = b"".join(archive.read(n) for n in names)
        assert key.encode() not in blob and b"17 + 25 = 42" not in blob
        plan = archive.read("workspace-plan.json").decode()
        assert '"managed_server"' in plan and '"operations"' in plan
        assert key.encode() not in (tmp_path / "ws" / "studio.sqlite3").read_bytes()
        assert key not in (tmp_path / "ws" / "logs" / "operations.jsonl").read_text()

        stopped = client.post(f"/api/projects/{pid}/managed/stop").json()
        assert stopped["status"] == "stopped" and fake.api_key(pid) is None
        state = client.get(f"/api/projects/{pid}/model").json()["model_endpoint"]["state"]
        assert state["status"] == "disconnected"


def test_restart_of_same_manifest_keeps_runs_comparable(tmp_path):
    app, _ = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        client.post(f"/api/projects/{pid}/model/evaluate")
        client.post(f"/api/projects/{pid}/managed/stop")
        assert (
            client.post(f"/api/projects/{pid}/managed/start", json={"consent": True}).status_code
            == 200
        )
        after = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"]
        repro = after["reproducibility"]
        assert repro["status"] == "identical" and repro["compared"] == 12
        assert repro["reference_launch_id"] != repro["current_launch_id"]
        assert all(run["matches_current_configuration"] for run in after["history"])


def test_crash_during_evaluation_is_recorded_and_requires_explicit_restart(tmp_path):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        cases = client.get(f"/api/projects/{pid}/model").json()["cases"]
        cases.insert(
            1,
            {
                "name": "Crash",
                "input": "CRASH now",
                "expected_behavior": "x",
                "expected_output": None,
            },
        )
        clean = [
            {
                k: c.get(k)
                for k in ("name", "input", "expected_behavior", "expected_output", "scoring")
                if c.get(k) is not None or k == "expected_output"
            }
            for c in cases
        ]
        # Editing cases needs the fixture idle only; the managed connection must reconnect.
        assert client.put(f"/api/projects/{pid}/cases", json={"cases": clean}).status_code == 200
        assert (
            client.post(f"/api/projects/{pid}/model/connect", json={"consent": True}).status_code
            == 200
        )
        run = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"][
            "evaluation"
        ]
        assert run["status"] == "interrupted"
        assert [r["status"] for r in run["results"]] == ["check_pass", "error"]
        failed = client.get(f"/api/projects/{pid}/managed").json()
        assert failed["status"] == "failed" and failed["reason"] == "server_exited_137"
        assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409
        assert (
            client.post(f"/api/projects/{pid}/managed/start", json={"consent": True}).status_code
            == 200
        )
        assert fake.started == 2


def test_start_failures_and_invalid_requests_are_explicit(tmp_path):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        assert (
            client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True}).json()[
                "detail"
            ]
            == "choose_a_managed_model_first"
        )
        assert (
            client.put(f"/api/projects/{pid}/managed", json={"model": "unknown"}).status_code == 422
        )
        assert (
            client.put(
                f"/api/projects/{pid}/managed", json={"model": MODEL, "memory_mb": 1}
            ).status_code
            == 422
        )
        assert client.put(f"/api/projects/{pid}/managed", json={"model": MODEL}).status_code == 200
        assert (
            client.post(f"/api/projects/{pid}/managed/start", json={"consent": False}).status_code
            == 422
        )
        assert (
            client.post(f"/api/projects/{pid}/managed/start", json={"consent": True}).json()[
                "detail"
            ]
            == "prepare_managed_model_first"
        )
        client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True})
        wait_for(client, pid, "prepared")
        fake.fail_ready = "server_out_of_memory"
        refused = client.post(f"/api/projects/{pid}/managed/start", json={"consent": True})
        assert refused.status_code == 409 and refused.json()["detail"] == "server_out_of_memory"
        view = client.get(f"/api/projects/{pid}/managed").json()
        assert view["status"] == "failed" and view["failure"]["oom_killed"] is True
        assert fake.api_key(pid) is None
        fake.fail_ready = None
        assert (
            client.post(f"/api/projects/{pid}/managed/start", json={"consent": True}).status_code
            == 200
        )
        assert (
            client.put(f"/api/projects/{pid}/managed", json={"model": MODEL}).json()["detail"]
            == "stop_managed_server_first"
        )
        client.delete(f"/api/projects/{pid}")
        assert fake.servers == {}


def test_cancelled_preparation_and_application_restart_leave_nothing_running(tmp_path):
    artifacts = FakeArtifacts(tmp_path)
    artifacts.block.clear()
    app, fake = build(tmp_path, artifacts=artifacts)
    with client_for(app) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        client.put(f"/api/projects/{pid}/managed", json={"model": MODEL})
        assert (
            client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True}).json()[
                "status"
            ]
            == "preparing"
        )
        client.post(f"/api/projects/{pid}/managed/cancel")
        failed = wait_for(client, pid, "failed")
        assert failed["reason"] == "download_cancelled"
        artifacts.block.set()
        client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True})
        wait_for(client, pid, "prepared")
        client.post(f"/api/projects/{pid}/managed/start", json={"consent": True})
    # Normal shutdown stops the managed server.
    assert fake.servers == {}
    store_app, _ = build(tmp_path, fake=fake, artifacts=artifacts)
    with client_for(store_app) as client:
        assert client.get(f"/api/projects/{pid}/managed").json()["status"] == "stopped"


def test_crashed_studio_session_is_recovered_on_next_start(tmp_path):
    artifacts = FakeArtifacts(tmp_path)
    app, fake = build(tmp_path, artifacts=artifacts)
    with client_for(app) as client:
        pid = ready_project(client)
        # Simulate a crash: shutdown hooks never ran, so the record still says ready
        # while the (Docker-owned) server keeps running.
        app.state.managed.close = lambda: None
    assert pid in fake.servers
    restarted, _ = build(tmp_path, fake=fake, artifacts=artifacts)
    with client_for(restarted) as client:
        view = client.get(f"/api/projects/{pid}/managed").json()
        assert view["status"] == "interrupted" and fake.servers == {}
        state = client.get(f"/api/projects/{pid}/model").json()["model_endpoint"]["state"]
        assert state["status"] == "disconnected"
        assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409


@pytest.mark.parametrize("path", ["managed/prepare", "managed/start"])
def test_managed_actions_require_the_session(tmp_path, path):
    app, _ = build(tmp_path)
    with TestClient(app, base_url="http://localhost") as client:
        pid = "0" * 32
        assert client.post(f"/api/projects/{pid}/{path}", json={"consent": True}).status_code == 401


def test_unreachable_cleanup_remains_pending_and_retries_on_reopen(tmp_path):
    artifacts = FakeArtifacts(tmp_path)
    app, fake = build(tmp_path, artifacts=artifacts)
    original_stop = fake.stop
    try:
        with client_for(app) as client:
            pid = ready_project(client)
            app.state.managed.close = lambda: None  # crashed process, owned server survives
        offline, _ = build(tmp_path, fake=fake, artifacts=artifacts)
        offline.state.managed._docker_reachable = lambda: False

        def unavailable_stop(pid):
            raise ServingFault("docker_unavailable")

        fake.stop = unavailable_stop
        with client_for(offline) as client:
            assert client.get(f"/api/projects/{pid}/managed").json()["status"] == "unknown"
            assert pid in fake.servers
            assert (
                client.put(f"/api/projects/{pid}/managed", json={"model": MODEL}).status_code == 409
            )
        fake.stop = original_stop
        online, _ = build(tmp_path, fake=fake, artifacts=artifacts)
        online.state.managed._docker_reachable = lambda: True
        with client_for(online) as client:
            assert client.get(f"/api/projects/{pid}/managed").json()["status"] == "interrupted"
            assert fake.servers == {}
            assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409
    finally:
        fake.stop = original_stop
        fake.recover()


def test_shutdown_retains_workspace_ownership_until_preparation_exits(tmp_path):
    entered, release, close_requested, exited = (threading.Event() for _ in range(4))
    errors = []

    class BlockedPull(FakeSupervisor):
        def pull(self, image, timeout=1800, cancel=None):
            entered.set()
            assert release.wait(20)

    app, _ = build(tmp_path, fake=BlockedPull())

    def own_workspace():
        try:
            with client_for(app) as client:
                pid = client.post("/api/examples/framework").json()["id"]
                client.put(f"/api/projects/{pid}/managed", json={"model": MODEL})
                client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True})
                assert close_requested.wait(20)
        except Exception as exc:
            errors.append(exc)
        finally:
            exited.set()

    owner = threading.Thread(target=own_workspace, daemon=True)
    owner.start()
    try:
        assert entered.wait(5), errors
        close_requested.set()
        assert not exited.wait(11), "Workspace ownership ended while preparation was still running"
        with pytest.raises(WorkspaceBusy), WorkspaceLease(tmp_path / "ws"):
            pytest.fail("Another Studio could own the still-active preparation workspace")
    finally:
        release.set()
        close_requested.set()
        owner.join(timeout=5)
    assert not owner.is_alive() and not errors
    assert app.state.managed.jobs == {}
    assert app.state.managed.store.all()[0]["managed_server"]["status"] == "failed"
    with WorkspaceLease(tmp_path / "ws"):
        pass


def test_removal_cancels_and_drains_preparation_before_deleting_record(tmp_path):
    entered = threading.Event()

    class WaitingArtifacts(FakeArtifacts):
        def fetch(self, artifact, progress=None, cancel=None):
            entered.set()
            return super().fetch(artifact, progress, cancel)

    artifacts = WaitingArtifacts(tmp_path)
    artifacts.block.clear()
    app, _ = build(tmp_path, artifacts=artifacts)
    with client_for(app) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        client.put(f"/api/projects/{pid}/managed", json={"model": MODEL})
        client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True})
        assert entered.wait(2)
        assert client.delete(f"/api/projects/{pid}").status_code == 204
        assert app.state.managed.jobs == {}, "Deletion returned with a live preparation writer"
        assert client.get("/api/projects").json() == []
        assert not artifacts.file.exists()


FIXTURE_CODE = str(
    (
        __import__("pathlib").Path(__file__).parents[3] / "packages/furnace/tests/adapter_fixture"
    ).resolve()
)
PY_IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


def custom(**overrides):
    python = {
        "image": PY_IMAGE,
        "code_path": FIXTURE_CODE,
        "entrypoint": "toy_adapter:Reverser",
        "model_id": "toy-reverser",
        "weights_path": None,
    }
    python.update(overrides)
    return {"model": "python-adapter", "python": python}


def test_custom_adapter_selection_is_validated_and_bound_to_its_code(tmp_path):
    app, _ = build(tmp_path)
    code = tmp_path / "adapter"
    code.mkdir()
    (code / "toy_adapter.py").write_text(
        (__import__("pathlib").Path(FIXTURE_CODE) / "toy_adapter.py").read_text(), encoding="utf-8"
    )
    with client_for(app) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        url = f"/api/projects/{pid}/managed"
        assert client.put(url, json={"model": "python-adapter"}).status_code == 422
        assert client.put(url, json={**custom(), "model": MODEL}).status_code == 422
        assert client.put(url, json=custom(code_path="relative/path")).status_code == 422
        assert client.put(url, json=custom(entrypoint="x; rm -rf /")).status_code == 422
        refused = client.put(url, json=custom(image="python:3.12-slim"))
        assert refused.status_code == 409 and refused.json()["detail"] == "adapter_image_not_pinned"
        first = client.put(url, json=custom(code_path=str(code))).json()["managed_server"]
        adapter = first["manifest"]["adapter"]
        assert adapter["code"]["basis"] == "file contents" and adapter["weights"] is None
        (code / "toy_adapter.py").write_text("# changed\n", encoding="utf-8")
        second = client.put(url, json=custom(code_path=str(code))).json()["managed_server"]
        assert second["manifest_sha256"] != first["manifest_sha256"]


def test_preflight_refuses_unavailable_gpu_and_oversized_limits(tmp_path):
    fake = FakeSupervisor()
    fake.daemon = lambda: {
        "status": "ready",
        "gpu_runtime": False,
        "cpus": 4,
        "memory_bytes": 4 * 2**30,
    }
    app, _ = build(tmp_path, fake=fake)
    with client_for(app) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        url = f"/api/projects/{pid}/managed"
        for selection, code in [
            ({"model": MODEL, "accelerator": "nvidia"}, "gpu_runtime_unavailable"),
            ({"model": MODEL, "memory_mb": 4096}, "memory_exceeds_docker_limit"),
            ({"model": MODEL, "cpus": 8}, "cpus_exceed_docker_limit"),
        ]:
            assert client.put(url, json=selection).status_code == 200
            refused = client.post(f"{url}/prepare", json={"consent": True})
            assert refused.status_code == 409 and refused.json()["detail"] == code
            assert client.get(url).json()["reason"] == code
        fake.daemon = lambda: {"status": "unavailable", "gpu_runtime": False}
        client.put(url, json={"model": MODEL})
        assert (
            client.post(f"{url}/prepare", json={"consent": True}).json()["detail"]
            == "docker_unavailable"
        )
