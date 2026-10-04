"""End-to-end: create a scan of fixture F1 through the API, run the job, read the Blueprint."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from furnace.jobs.worker import run_one
from furnace_api.main import app

pytestmark = pytest.mark.db


def _drain_cpu_queue():
    import furnace.jobs.handlers  # noqa: F401

    async def go():
        while await run_one("test-worker", ["cpu"]):
            pass

    asyncio.run(go())


def test_fixture_scan_end_to_end():
    with TestClient(app) as c:
        r = c.post("/api/public/scans", json={"kind": "fixture", "value": "support-rag-py"})
        assert r.status_code == 201, r.text
        scan_id = r.json()["scan_id"]
        assert c.get(f"/api/scans/{scan_id}").json()["status"] == "queued"
        _drain_cpu_queue()
        scan = c.get(f"/api/scans/{scan_id}").json()
        assert scan["status"] == "succeeded", scan
        assert scan["stats"]["recommendations"] >= 5

        bp = c.get(f"/api/scans/{scan_id}/blueprint").json()
        rules = {r["rule_id"] for r in bp["recommendations"]}
        assert {"rel.llm_timeout", "eval.citation_contract", "inf.prefix_stability_guard"} <= rules
        # every recommendation's evidence resolves to a stored excerpt with a file locator
        for rec in bp["recommendations"]:
            for eid in rec["evidence_ids"]:
                assert eid in bp["evidence"], (rec["rule_id"], eid)
        contradictions = bp["appspec"]["contradictions"]
        assert any(c["predicate"] == "model" for c in contradictions)

        g = c.get(f"/api/scans/{scan_id}/graph").json()
        assert any(n["key"] == "route:POST /chat" for n in g["nodes"])

        events = c.get(f"/api/scans/{scan_id}/events")
        assert "Blueprint ready" in events.text


def test_github_input_validation():
    with TestClient(app) as c:
        r = c.post("/api/public/scans", json={"kind": "github", "value": "not a repo url"})
        assert r.status_code == 422


def test_upload_requires_single_zip():
    with TestClient(app) as c:
        r = c.post(
            "/api/public/scans/upload", files={"files": ("notes.txt", b"hello", "text/plain")}
        )
        assert r.status_code == 422
