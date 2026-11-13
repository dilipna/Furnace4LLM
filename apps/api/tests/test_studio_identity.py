import io
import json
import zipfile

from fastapi.testclient import TestClient
from furnace_api.studio import create_app
from furnace_api.studio_evidence import configuration_identity

TOKEN = "identity-local-test-session-" * 3


def test_project_identity_export_revision_and_relevant_input_invalidation(tmp_path):
    app = create_app(tmp_path / "workspace", TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        example = client.post("/api/examples/framework").json()
        other_folder = tmp_path / "other"
        other_folder.mkdir()
        other = client.post(
            "/api/projects", json={"name": "Other project", "path": str(other_folder)}
        ).json()
        # Even identical declared inputs belong to different project identities.
        same = {**example, "id": other["id"]}
        assert configuration_identity(same) != example["configuration_sha256"]
        prior = example
        changes = [
            ("contract", {"notes": "Pinned loading changed"}),
            (
                "plan",
                {
                    "compute": "customer",
                    "memory_gb": 4,
                    "timeout_seconds": 1,
                    "log_retention_days": 7,
                },
            ),
            (
                "cases",
                {
                    "cases": [
                        {
                            "name": "Changed",
                            "input": "different",
                            "expected_behavior": "exact",
                            "expected_output": "framework:DIFFERENT",
                        }
                    ]
                },
            ),
        ]
        for field, value in changes:
            changed = client.put(f"/api/projects/{example['id']}/{field}", json=value).json()
            assert changed["revision"] > prior["revision"]
            assert changed["configuration_sha256"] != prior["configuration_sha256"]
            assert changed["evaluation_verification"] == "no_current_evidence"
            assert all(case["status"] == "not_run" for case in changed["cases"])
            prior = changed
        with zipfile.ZipFile(
            io.BytesIO(client.post(f"/api/projects/{example['id']}/kit").content)
        ) as archive:
            provenance = json.loads(archive.read("workspace-plan.json"))["provenance"]
            assert provenance["project_id"] == example["id"]
            assert provenance["configuration_sha256"] == prior["configuration_sha256"]
            assert provenance["verification_status"] == "no_current_evidence"
            assert provenance["execution_kind"] == "not_run"
            assert b"not model latency" in archive.read("README.md")
        assert client.get(f"/api/projects/{other['id']}").json()["revision"] == 0
        assert (
            "real research-model adapter is implemented or validated" in client.get("/guide").text
        )
