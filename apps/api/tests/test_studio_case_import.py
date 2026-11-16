"""Conditional suite replacement uses the existing saved-case validation and locks."""

import threading

from fastapi.testclient import TestClient
from furnace_api.studio import create_app

TOKEN = "case-import-local-test-session-" * 3
CASE = {"name": "Imported", "input": "sanitized", "expected_behavior": "Unscored description"}


def test_conditional_replacement_resets_labels_and_refuses_stale_or_foreign_identity(
    tmp_path, monkeypatch
):
    app = create_app(tmp_path, TOKEN)

    def no_docker(*args, **kwargs):
        raise AssertionError("Case replacement must not execute Docker")

    monkeypatch.setattr(app.state.runtime.manager, "_docker", no_docker)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        original = client.post("/api/examples/framework").json()
        pid = original["id"]
        path = f"/api/projects/{pid}/cases"
        body = {"cases": [CASE], "expected_configuration_sha256": original["configuration_sha256"]}
        saved = client.put(path, json=body).json()
        assert saved["cases"] == [{**CASE, "expected_output": None, "status": "not_run"}]
        assert saved["evaluation"] is None
        assert saved["configuration_sha256"] != original["configuration_sha256"]
        refused = client.put(path, json=body)
        assert refused.status_code == 409 and "changed after preview" in refused.json()["detail"]
        assert client.get(f"/api/projects/{pid}/model").json()["revision"] == saved["revision"]
        assert (
            client.put(path, json={**body, "expected_configuration_sha256": "x"}).status_code == 422
        )
        assert (
            client.put(path, json={"cases": [{**CASE, "status": "framework_pass"}]}).status_code
            == 422
        )
        other_folder = tmp_path / "other"
        other_folder.mkdir()
        other = client.post(
            "/api/projects", json={"name": "Other", "path": str(other_folder)}
        ).json()
        assert (
            client.put(
                path, json={**body, "expected_configuration_sha256": other["configuration_sha256"]}
            ).status_code
            == 409
        )
        asset = client.get("/assets/case-import.mjs")
        assert asset.status_code == 200 and "javascript" in asset.headers["content-type"]


def test_case_import_checks_identity_after_waiting_for_project_lock(tmp_path):
    app = create_app(tmp_path, TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        original = client.post("/api/examples/framework").json()
        pid, responses = original["id"], []
        entered = threading.Event()

        def replace():
            entered.set()
            responses.append(
                client.put(
                    f"/api/projects/{pid}/cases",
                    json={
                        "cases": [CASE],
                        "expected_configuration_sha256": original["configuration_sha256"],
                    },
                )
            )

        with app.state.runtime.manager.lock_for(pid):
            worker = threading.Thread(target=replace)
            worker.start()
            assert entered.wait(timeout=2)
            changed = app.state.runtime.update(
                pid,
                "contract",
                {**original["contract"], "notes": "Edited while import waits"},
                "Concurrent edit",
            )
        worker.join(timeout=3)
        assert not worker.is_alive()
        assert responses[0].status_code == 409
        stored = client.get(f"/api/projects/{pid}/model").json()
        assert stored["revision"] == changed["revision"]
        assert stored["cases"] == changed["cases"]
        assert stored["contract"]["notes"] == "Edited while import waits"
