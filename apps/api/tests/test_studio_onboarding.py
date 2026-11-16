import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from furnace.runtime.manager import RuntimeFault
from furnace_api.studio import create_app

TOKEN = "onboarding-local-session-" * 3


def test_guided_example_is_real_persistent_metadata_without_execution(tmp_path, monkeypatch):
    app = create_app(tmp_path, TOKEN)
    manager = app.state.runtime.manager

    def no_docker(*args, **kwargs):
        pytest.fail("Opening/exporting a guided example must not contact Docker")

    monkeypatch.setattr(manager, "_docker", no_docker)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        assert (
            client.post(
                "/api/examples/framework", headers={"x-furnace-session": "wrong"}
            ).status_code
            == 401
        )
        first = client.post("/api/examples/framework").json()
        pid = first["id"]
        assert first["origin"] == "guided_example"
        assert first["runtime"] == "not_connected" and first["evaluation"] is None
        assert not first["assessment"]["execution_performed"]
        assert not first["assessment"]["file_evidence"]["checkpoint_file_present"]
        assert [case["status"] for case in first["cases"]] == ["not_run", "not_run"]
        assert first["cases"][0]["expected_output"] == "framework:HELLO FURNACE"
        assert first["cases"][1]["expected_output"] is None
        client.put(f"/api/projects/{pid}/contract", json={"notes": "My preserved draft contract"})
        again = client.post("/api/examples/framework").json()
        assert again["id"] == pid and again["contract"]["notes"] == "My preserved draft contract"
        assert len(client.get("/api/projects").json()) == 1
        kit = client.post(f"/api/projects/{pid}/kit")
        with zipfile.ZipFile(io.BytesIO(kit.content)) as archive:
            assert json.loads(archive.read("assessment.json")) == first["assessment"]
            assert json.loads(archive.read("workspace-plan.json"))["plan"]["billing"] == "inactive"
            assert len(archive.read("evaluation-cases.example.jsonl").splitlines()) == 2
    with TestClient(
        create_app(tmp_path, TOKEN),
        base_url="http://localhost",
        headers={"x-furnace-session": TOKEN},
    ) as client:
        assert client.post("/api/examples/framework").json()["id"] == pid


def test_example_respects_two_project_limit_without_creating_hidden_records(tmp_path):
    app = create_app(tmp_path / "workspace", TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        for index in range(2):
            folder = tmp_path / str(index)
            folder.mkdir()
            assert (
                client.post(
                    "/api/projects", json={"name": str(index), "path": str(folder)}
                ).status_code
                == 201
            )
        assert client.post("/api/examples/framework").status_code == 409
        assert len(client.get("/api/projects").json()) == 2


def test_system_check_keeps_workspace_available_when_docker_is_unreachable(tmp_path, monkeypatch):
    app = create_app(tmp_path, TOKEN)
    monkeypatch.setattr(
        app.state.runtime.manager,
        "_docker",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeFault("docker_unavailable")),
    )
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        assert client.get("/api/system", headers={"x-furnace-session": "wrong"}).status_code == 401
        system = client.get("/api/system").json()
        assert system["workspace"] == "available"
        assert system["runtime"] == {"status": "unavailable", "code": "docker_unavailable"}
        assert system["model_compatibility"] == "not_verified"
        assert client.post("/api/examples/framework").status_code == 200
