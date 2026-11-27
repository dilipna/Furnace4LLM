"""A CLI-exported starter suite must be usable by Studio, not just valid JSON."""

import json

from fastapi.testclient import TestClient
from furnace.starter import export_starter
from furnace_api.studio import create_app

TOKEN = "starter-handoff-test-session-" * 3


def test_cli_starter_cases_can_be_saved_without_becoming_execution_evidence(tmp_path):
    source = tmp_path / "research-model"
    source.mkdir()
    kit = tmp_path / "starter"
    export_starter(source, kit)
    # The browser importer discards historical status; it does not rename fields
    # or invent missing inputs/expectations. The API must accept that same shape.
    cases = [
        {key: value for key, value in json.loads(line).items() if key != "status"}
        for line in (kit / "evaluation-cases.example.jsonl").read_text().splitlines()
    ]
    with TestClient(
        create_app(tmp_path / "workspace", TOKEN),
        base_url="http://localhost",
        headers={"x-furnace-session": TOKEN},
    ) as client:
        project = client.post(
            "/api/projects", json={"name": "Research model", "path": str(source)}
        ).json()
        saved = client.put(f"/api/projects/{project['id']}/cases", json={"cases": cases})
        assert saved.status_code == 200, saved.text
        record = saved.json()
        assert len(record["cases"]) == len(cases) > 0
        assert all(case["status"] == "not_run" for case in record["cases"])
        assert record["evaluation"] is None
        assert record["model_endpoint"]["evaluation"] is None
        assert record["runtime"] == "not_connected"
