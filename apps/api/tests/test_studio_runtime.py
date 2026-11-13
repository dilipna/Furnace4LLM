import json

import pytest
from fastapi.testclient import TestClient
from furnace.runtime.lease import WorkspaceBusy
from furnace.runtime.manager import RuntimeFault
from furnace_api.studio import create_app

TOKEN = "local-runtime-api-check-" * 3


def project_and_plan(client, folder):
    folder.mkdir()
    (folder / "research.py").write_text("raise RuntimeError('untrusted model must not execute')")
    (folder / ".env").write_text("FURNACE_PRIVATE_TEST_SECRET=must-not-mount")
    project = client.post(
        "/api/projects", json={"name": "Runtime fixture, not model", "path": str(folder)}
    ).json()
    pid = project["id"]
    assert (
        client.put(
            f"/api/projects/{pid}/plan",
            json={
                "compute": "customer",
                "memory_gb": 4,
                "timeout_seconds": 1,
                "log_retention_days": 7,
            },
        ).status_code
        == 200
    )
    return pid


def start(client, pid):
    response = client.post(
        f"/api/projects/{pid}/start", json={"adapter": "framework_fixture", "consent": True}
    )
    assert response.status_code == 200, response.text
    return response.json()["runtime"]


def test_real_api_worker_requests_evaluations_edits_export_and_removal(tmp_path):
    app = create_app(tmp_path / "workspace", TOKEN)
    manager = app.state.runtime.manager
    manager.prepare()
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = project_and_plan(client, tmp_path / "model")
        assert (
            client.post(
                f"/api/projects/{pid}/start",
                json={"adapter": "framework_fixture", "consent": False},
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/projects/{pid}/start", json={"adapter": "unreviewed_python", "consent": True}
            ).status_code
            == 422
        )
        cases = [
            {
                "name": "match",
                "input": "hello",
                "expected_behavior": "fixture protocol",
                "expected_output": "framework:HELLO",
            },
            {
                "name": "mismatch",
                "input": "world",
                "expected_behavior": "intentionally wrong assertion",
                "expected_output": "wrong",
            },
            {
                "name": "description",
                "input": "other",
                "expected_behavior": "natural language expectation is not a score",
            },
        ]
        assert client.put(f"/api/projects/{pid}/cases", json={"cases": cases}).status_code == 200
        first = start(client, pid)
        assert first["container_id"] == start(client, pid)["container_id"]
        response = client.post(
            f"/api/projects/{pid}/predict", json={"input": "sensitive-request-content"}
        )
        assert response.json()["output"] == "framework:SENSITIVE-REQUEST-CONTENT"
        project = client.get(f"/api/projects/{pid}").json()
        assert "sensitive-request-content" not in json.dumps(project["events"])
        assert "SENSITIVE-REQUEST-CONTENT" not in json.dumps(project["events"])
        assert client.put(f"/api/projects/{pid}/cases", json={"cases": cases}).status_code == 409
        result = client.post(f"/api/projects/{pid}/evaluate").json()
        assert [c["status"] for c in result["cases"]] == [
            "framework_pass",
            "framework_fail",
            "unscored",
        ]
        assert result["evaluation"]["model_execution"] is False
        assert result["evaluation"]["status"] == "completed"
        again = client.post(f"/api/projects/{pid}/evaluate").json()
        assert (
            again["evaluation"]["configuration_sha256"]
            == result["evaluation"]["configuration_sha256"]
        )
        assert (
            again["evaluation"]["results"][0]["request_id"]
            != result["evaluation"]["results"][0]["request_id"]
        )
        assert client.post(f"/api/projects/{pid}/stop").json()["runtime"]["status"] == "stopped"
        assert manager.inspect(pid) is None
        assert (
            client.put(f"/api/projects/{pid}/cases", json={"cases": cases[:1]}).json()["evaluation"]
            is None
        )
        start(client, pid)
        assert client.delete(f"/api/projects/{pid}").status_code == 204
        assert manager.inspect(pid) is None
        assert (tmp_path / "model" / "research.py").is_file()


def test_application_restart_and_shutdown_remove_owned_workers(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, TOKEN)
    manager = app.state.runtime.manager
    manager.prepare()
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = project_and_plan(client, tmp_path / "model")
        first = start(client, pid)
        concurrent = create_app(workspace, TOKEN + "concurrent")
        with pytest.raises(WorkspaceBusy, match="already open"), TestClient(concurrent):
            pytest.fail("second application acquired a live workspace")
        info = manager.inspect(pid)
        assert info is not None and info["State"]["Running"]
        assert info["Id"] == first["container_id"]
        assert (
            client.post(f"/api/projects/{pid}/predict", json={"input": "still alive"}).json()[
                "output"
            ]
            == "framework:STILL ALIVE"
        )
    assert manager.inspect(pid) is None  # normal shutdown stops the worker
    # Create an actual orphan worker + persisted active state without a live app lease.
    orphan = manager.start(pid)
    app.state.runtime.store.change(pid, "runtime", orphan, "orphan fixture")
    other = create_app(workspace, TOKEN + "new")
    with TestClient(
        other, base_url="http://localhost", headers={"x-furnace-session": TOKEN + "new"}
    ) as second:
        assert manager.inspect(pid) is None
        assert second.get(f"/api/projects/{pid}").json()["runtime"]["status"] == "interrupted"
        restarted = start(second, pid)
        assert restarted["container_id"] not in {first["container_id"], orphan["container_id"]}
    assert manager.inspect(pid) is None
    assert other.state.runtime.store.get(pid)["runtime"]["status"] == "stopped"


def test_interrupted_evaluation_preserves_actual_case_states(tmp_path, monkeypatch):
    app = create_app(tmp_path / "workspace", TOKEN)
    manager = app.state.runtime.manager
    manager.prepare()
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = project_and_plan(client, tmp_path / "model")
        cases = [
            {
                "name": str(i),
                "input": "hello",
                "expected_behavior": "fixture",
                "expected_output": "framework:HELLO",
            }
            for i in range(3)
        ]
        client.put(f"/api/projects/{pid}/cases", json={"cases": cases})
        start(client, pid)
        original = manager.predict
        calls = 0

        def die_between_cases(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                manager._docker("kill", manager.name(pid))
            return original(*args, **kwargs)

        monkeypatch.setattr(manager, "predict", die_between_cases)
        result = client.post(f"/api/projects/{pid}/evaluate").json()
        assert result["evaluation"]["status"] == "interrupted"
        assert [c["status"] for c in result["cases"]] == ["framework_pass", "error", "not_run"]
        assert result["runtime"]["status"] == "failed"
        assert manager.inspect(pid) is None
        assert calls == 2
        # Refresh must retain the concrete failure and must not add repeated absence events.
        refreshed = client.get(f"/api/projects/{pid}").json()
        assert refreshed["runtime"] == result["runtime"]
        assert refreshed["events"] == result["events"]


def test_cleanup_failure_remains_unknown_not_stopped(tmp_path, monkeypatch):
    app = create_app(tmp_path / "workspace", TOKEN)
    service = app.state.runtime
    # No real worker in this failure-path unit case: represent unreachable Docker.
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = project_and_plan(client, tmp_path / "model")
        service.store.change(
            pid, "runtime", {"status": "ready", "adapter": "framework_fixture"}, "test state"
        )
        monkeypatch.setattr(
            service.manager,
            "stop",
            lambda *_: (_ for _ in ()).throw(RuntimeFault("docker_unavailable")),
        )
        response = client.post(f"/api/projects/{pid}/stop")
        assert response.status_code == 409
        assert service.store.get(pid)["runtime"]["status"] == "unknown"
        assert client.delete(f"/api/projects/{pid}").status_code == 409
        assert service.store.get(pid)["id"] == pid


def test_batch_time_budget_does_not_execute_remaining_cases(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from furnace_api import studio_runtime

    app = create_app(tmp_path / "workspace", TOKEN)
    manager = app.state.runtime.manager
    manager.prepare()
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = project_and_plan(client, tmp_path / "model")
        cases = [
            {
                "name": str(i),
                "input": "hello",
                "expected_behavior": "fixture",
                "expected_output": "framework:HELLO",
            }
            for i in range(3)
        ]
        client.put(f"/api/projects/{pid}/cases", json={"cases": cases})
        start(client, pid)
        ticks = iter([0, 0, 31])
        monkeypatch.setattr(studio_runtime, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
        result = client.post(f"/api/projects/{pid}/evaluate").json()
        assert result["evaluation"]["status"] == "interrupted"
        assert [c["status"] for c in result["cases"]] == ["framework_pass", "not_run", "not_run"]
        assert result["evaluation"]["results"][1]["reason"] == "evaluation_time_budget_exhausted"
        assert manager.inspect(pid) is None


def test_restart_keeps_partial_evaluation_evidence_without_promoting_missing_cases(tmp_path):
    app = create_app(tmp_path / "workspace", TOKEN)
    service = app.state.runtime
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = project_and_plan(client, tmp_path / "model")
    service.store.change(
        pid,
        "cases",
        [{"status": "framework_pass"}, {"status": "not_run"}],
        "partial evidence",
        extra={
            "evaluation": {
                "status": "running",
                "model_execution": False,
                "results": [{"case_index": 0, "status": "framework_pass"}],
            }
        },
    )
    restarted = create_app(tmp_path / "workspace", TOKEN + "new")
    with TestClient(
        restarted, base_url="http://localhost", headers={"x-furnace-session": TOKEN + "new"}
    ) as client:
        result = client.get(f"/api/projects/{pid}").json()
        assert result["evaluation"]["status"] == "interrupted"
        assert [c["status"] for c in result["cases"]] == ["framework_pass", "not_run"]
        assert len(result["evaluation"]["results"]) == 1
