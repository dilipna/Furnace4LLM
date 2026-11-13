import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from furnace_api.studio import create_app

TOKEN = "studio-test-token-" * 3


@pytest.fixture
def setup(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text('{"model_type":"test_metadata_only"}')
    (model / "research.py").write_text("raise RuntimeError('must never execute')")
    app = create_app(tmp_path / "workspace", TOKEN)
    client = TestClient(app, base_url="http://localhost", headers={"x-furnace-session": TOKEN})
    return client, model, tmp_path


def add(client, model):
    response = client.post("/api/projects", json={"name": "Research model", "path": str(model)})
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_workspace_roundtrip_export_and_restart(setup):
    client, model, root = setup
    project = add(client, model)
    pid = project["id"]
    assert project["runtime"] == "not_connected"
    assert not project["assessment"]["execution_performed"]
    contract = {
        "architecture": "Experimental recurrent",
        "task": "text_generation",
        "device": "cpu",
    }
    assert client.put(f"/api/projects/{pid}/contract", json=contract).status_code == 200
    plan = {"compute": "customer", "memory_gb": 4, "timeout_seconds": 20, "log_retention_days": 7}
    result = client.put(f"/api/projects/{pid}/plan", json=plan).json()
    assert result["plan"]["billing"] == "inactive"
    assert result["plan"]["provisioning"] == "not_started"
    assert result["plan"]["subscription_usd_month"] == 20
    cases = {
        "cases": [
            {
                "name": "A representative case",
                "input": "sanitized input",
                "expected_behavior": "author supplied expectation",
            }
        ]
    }
    assert (
        client.put(f"/api/projects/{pid}/cases", json=cases).json()["cases"][0]["status"]
        == "not_run"
    )
    # Source can change after assessment; exporting uses the saved snapshot.
    (model / "config.json").write_text("invalid source changed later")
    result = client.post(f"/api/projects/{pid}/kit")
    assert result.status_code == 200
    with zipfile.ZipFile(io.BytesIO(result.content)) as kit:
        assert len(kit.namelist()) == 6
        assert json.loads(kit.read("assessment.json")) == project["assessment"]
        assert (
            json.loads(kit.read("model-contract.json"))["architecture"] == "Experimental recurrent"
        )
        assert json.loads(kit.read("evaluation-cases.example.jsonl"))["status"] == "not_run"
        assert json.loads(kit.read("workspace-plan.json"))["plan"]["compute"] == "customer"
    other = TestClient(
        create_app(root / "workspace", TOKEN + "new"),
        base_url="http://localhost",
        headers={"x-furnace-session": TOKEN + "new"},
    )
    saved = other.get(f"/api/projects/{pid}").json()
    assert saved["cases"][0]["name"] == "A representative case"
    assert len(saved["events"]) == 4
    assert "sanitized input" not in json.dumps(saved["events"])
    assert other.get("/api/projects", headers={"x-furnace-session": TOKEN}).status_code == 401
    assert client.post(f"/api/projects/{pid}/start").status_code == 409
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert (model / "research.py").exists()
    assert other.get("/api/projects").json() == []


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/projects"),
        ("post", "/api/projects"),
        ("post", "/api/projects/unknown/kit"),
        ("delete", "/api/projects/unknown"),
    ],
)
def test_no_local_files_without_session(setup, method, path):
    client, _, _ = setup
    assert getattr(client, method)(path, headers={"x-furnace-session": "wrong"}).status_code == 401


def test_cross_origin_host_and_payload_guards(setup):
    client, model, _ = setup
    assert (
        client.post(
            "/api/projects",
            headers={"origin": "https://evil.example"},
            json={"name": "x", "path": str(model)},
        ).status_code
        == 403
    )
    assert client.get("/api/projects", headers={"host": "evil.example"}).status_code == 400
    assert client.post("/api/projects", content=b"x" * 65537).status_code == 413
    assert client.post("/api/projects", content=b"{bad").status_code == 422
    assert (
        client.post(
            "/api/projects", json={"name": "x", "path": str(model), "execute": True}
        ).status_code
        == 422
    )
    assert client.get("/assets/missing.txt").status_code == 422
    assert client.get("/").headers["content-security-policy"].startswith("default-src 'self'")
    assert client.get("/").headers["cache-control"] == "no-store"


def test_model_limit_duplicate_missing_and_validation(setup):
    client, model, root = setup
    first = add(client, model)
    assert add(client, model)["id"] == first["id"]
    for name in ["second", "third"]:
        (root / name).mkdir()
    assert (
        client.post(
            "/api/projects", json={"name": "second", "path": str(root / "second")}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/projects", json={"name": "third", "path": str(root / "third")}
        ).status_code
        == 409
    )
    assert len(client.get("/api/projects").json()) == 2
    assert (
        client.post("/api/projects", json={"name": "bad", "path": str(root / "absent")}).status_code
        == 422
    )
    pid = first["id"]
    assert (
        client.put(
            f"/api/projects/{pid}/plan",
            json={
                "compute": "furnace",
                "memory_gb": 0,
                "timeout_seconds": 10,
                "log_retention_days": 7,
            },
        ).status_code
        == 422
    )
    assert (
        client.put(f"/api/projects/{pid}/contract", json={"task": "arbitrary-code"}).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/projects/{pid}/cases",
            json={"cases": [{"name": "x", "input": "", "expected_behavior": "x"}]},
        ).status_code
        == 422
    )
    assert client.get("/api/projects/missing").status_code == 404


def test_startup_and_assets_are_real_local_application(setup):
    client, _, _ = setup
    assert client.get("/healthz").json() == {
        "studio": "ready",
        "model_runtime": "not_connected",
        "billing": "inactive",
    }
    assert "Your model is the research" in client.get("/").text
    assert client.get("/assets/studio.js").status_code == 200
    assert client.get("/assets/studio.css").status_code == 200
    with pytest.raises(ValueError, match="strong"):
        create_app(Path("unused"), "short")
