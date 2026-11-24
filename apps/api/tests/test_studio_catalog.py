"""Recipe discovery remains available before Docker is installed or working."""

import json
import subprocess

import pytest
from fastapi.testclient import TestClient
from furnace.runtime import serving
from furnace.runtime.serving import ServingFault
from furnace_api.studio import create_app

TOKEN = "catalog-first-use-test-session-" * 3


@pytest.mark.parametrize("failure", ["missing_cli", "unavailable", "inspection_timeout"])
def test_catalog_without_working_docker_preserves_metadata_and_idle_state(
    tmp_path, monkeypatch, failure
):
    if failure == "missing_cli":
        original = serving.shutil.which
        monkeypatch.setattr(
            serving.shutil, "which", lambda name: None if name == "docker" else original(name)
        )
    else:

        def docker(self, *args, **kwargs):
            if args[0] == "info" and failure == "inspection_timeout":
                return subprocess.CompletedProcess(
                    args, 0, json.dumps({"OSType": "linux", "Runtimes": {}}), ""
                )
            if args[0] == "info" or failure == "inspection_timeout":
                raise ServingFault(
                    "docker_timeout" if failure == "inspection_timeout" else "docker_unavailable"
                )
            return subprocess.CompletedProcess(args, 1, "", "Cannot connect to daemon")

        monkeypatch.setattr(serving.Supervisor, "_docker", docker)
    app = create_app(tmp_path / "workspace", TOKEN)
    with TestClient(
        app,
        base_url="http://localhost",
        headers={"x-furnace-session": TOKEN},
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/managed/catalog")
        assert response.status_code == 200
        catalog = response.json()
        assert catalog["docker"]["status"] == "unavailable"
        assert catalog["docker"]["gpu_runtime"] is False
        assert {model["id"] for model in catalog["models"]} == {
            "qwen2.5-1.5b-instruct-q4_k_m",
            "qwen2.5-0.5b-instruct-q8_0",
            "granite-4.0-h-350m-q8_0",
        }
        assert all(
            present is None
            for model in catalog["models"]
            for present in model["images_present"].values()
        )
        assert client.get("/api/projects").json() == []
        assert app.state.managed.jobs == {}
