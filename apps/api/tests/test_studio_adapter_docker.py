"""A researcher's own adapter through Studio on real Docker. Requires local Docker.

The adapter is the deterministic test reverser (not a model): this checks that Studio
prepares, starts, connects, evaluates, observes and stops a custom adapter image with
the same isolation and evidence rules as the pinned recipes.
"""

import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient
from furnace.runtime.serving import workspace_scope
from furnace_api.studio import create_app

TOKEN = "studio-custom-adapter-docker-test-session-" * 2
CODE = Path(__file__).resolve().parents[3] / "packages" / "furnace" / "tests" / "adapter_fixture"
IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


def labelled(workspace: Path) -> list[str]:
    scope = f"label=furnace.managed.workspace={workspace_scope(workspace)}"
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", scope, "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


def test_custom_adapter_runs_isolated_with_honest_evidence(tmp_path):
    workspace = tmp_path / "ws"
    app = create_app(workspace, TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        selection = {
            "model": "python-adapter",
            "memory_mb": 512,
            "cpus": 1,
            "request_timeout_seconds": 10,
            "python": {
                "image": IMAGE,
                "code_path": str(CODE),
                "entrypoint": "toy_adapter:Reverser",
                "model_id": "toy-reverser",
            },
        }
        assert client.put(f"/api/projects/{pid}/managed", json=selection).status_code == 200
        client.post(f"/api/projects/{pid}/managed/prepare", json={"consent": True})
        deadline = time.monotonic() + 600
        while client.get(f"/api/projects/{pid}/managed").json()["status"] == "preparing":
            assert time.monotonic() < deadline
            time.sleep(0.5)
        assert client.get(f"/api/projects/{pid}/managed").json()["status"] == "prepared"
        assert client.post(f"/api/projects/{pid}/managed/suite").status_code == 200
        started = client.post(f"/api/projects/{pid}/managed/start", json={"consent": True})
        assert started.status_code == 200, started.text
        try:
            endpoint = client.get(f"/api/projects/{pid}/model").json()["model_endpoint"]
            assert endpoint["state"]["status"] == "connected"
            assert endpoint["server_managed_by_furnace"] is True
            assert endpoint["weights_verified_before_launch"] is False
            assert endpoint["connection"]["server"]["engine"] == "python-adapter"
            reply = client.post(f"/api/projects/{pid}/model/predict", json={"input": "abc"})
            assert reply.json()["output"] == "reversed:cba state=1"
            run = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"]
            evaluation = run["evaluation"]
            assert evaluation["status"] == "completed" and len(evaluation["results"]) == 12
            assert evaluation["weights_verified_before_launch"] is False
            assert all(r["status"] in {"check_pass", "check_fail"} for r in evaluation["results"])
            observed = client.get(f"/api/projects/{pid}/managed/observe").json()
            assert observed["container"]["running"] is True
            assert observed["metrics"]["furnace_adapter:requests_total"] == 13.0
            assert len(labelled(workspace)) == 2
        finally:
            stopped = client.post(f"/api/projects/{pid}/managed/stop").json()
        assert stopped["status"] == "stopped"
        assert labelled(workspace) == []
