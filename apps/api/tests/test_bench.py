"""FurnaceBench read API and the labeling endpoint, against a temporary bench directory."""

import json

import pytest
from fastapi.testclient import TestClient
from furnace.settings import get_settings
from furnace_api.routers import bench


@pytest.fixture
def client(tmp_path, monkeypatch):
    camp = tmp_path / "results" / "2026-10-06"
    (camp / "rq4").mkdir(parents=True)
    (camp / "rq1.json").write_text(
        json.dumps({"apps": [{"app": "a", "appspec": {"big": 1}}], "micro": {}})
    )
    (camp / "rq4" / "rq4.json").write_text(json.dumps({"rows": [1]}))
    (camp / "REPORT.md").write_text("# report")
    (camp / "rq3").mkdir()
    (camp / "rq3" / "r1_dynamic_head.targeted.check.md").write_text("# 1 regression found")
    (tmp_path / "results" / "not-a-campaign").mkdir()
    (tmp_path / "labels").mkdir()
    (tmp_path / "labels" / "f1_queue.jsonl").write_text(
        json.dumps({"id": "f1-001", "answer": "x"})
        + "\n"
        + json.dumps({"id": "f1-002", "answer": "y"})
        + "\n"
    )
    monkeypatch.setenv("FURNACE_BENCH_DIR", str(tmp_path))
    get_settings.cache_clear()
    # A plain FastAPI app with only the bench router: no database needed.
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(bench.router)
    yield TestClient(app), tmp_path
    get_settings.cache_clear()


def test_campaigns_and_results(client):
    c, _ = client
    camps = c.get("/api/bench/campaigns").json()
    assert [x["name"] for x in camps] == ["2026-10-06"]
    assert set(camps[0]["available"]) == {"rq1", "rq4"} and camps[0]["has_report"]
    assert c.get("/api/bench/campaigns/2026-10-06").json()["report_md"] == "# report"
    assert c.get("/api/bench/campaigns/2026-10-06/rq4").json() == {"rows": [1]}
    assert "appspec" not in c.get("/api/bench/campaigns/2026-10-06/rq1").json()["apps"][0]
    assert c.get("/api/bench/campaigns/2026-10-06/rq5").status_code == 404
    assert (
        c.get("/api/bench/campaigns/2026-10-06/rq3/r1_dynamic_head/check")
        .json()["markdown"]
        .startswith("# 1")
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/bench/campaigns/..%2F..%2Fsecrets",
        "/api/bench/campaigns/not-a-campaign",
        "/api/bench/campaigns/2026-10-06/..%2Frq4",
        "/api/bench/campaigns/2026-10-06/rq3/..%2F..%2FREPORT/check",
    ],
)
def test_paths_cannot_escape_the_results_dir(client, path):
    c, _ = client
    assert c.get(path).status_code == 404


def test_labels_upsert_and_validation(client):
    c, root = client
    q = c.get("/api/labels/queue").json()
    assert (
        [i["id"] for i in q["items"]] == ["f1-001", "f1-002"]
        and q["labels"] == {}
        and q["writable"]
    )
    assert (
        c.post(
            "/api/labels", json={"id": "f1-001", "grounded": False, "correct": False}
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/api/labels", json={"id": "f1-001", "grounded": True, "correct": None, "notes": "ok"}
        ).status_code
        == 201
    )
    assert c.post("/api/labels", json={"id": "nope", "grounded": True}).status_code == 404
    rows = [json.loads(x) for x in (root / "labels" / "f1_labels.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["grounded"] is True and rows[0]["notes"] == "ok"
    assert c.get("/api/labels/queue").json()["labels"]["f1-001"]["grounded"] is True


def test_labels_read_only_deployment(client, monkeypatch):
    c, _ = client
    monkeypatch.setenv("FURNACE_LABELS_WRITABLE", "false")
    get_settings.cache_clear()
    assert c.post("/api/labels", json={"id": "f1-001", "grounded": True}).status_code == 403
    assert c.get("/api/labels/queue").json()["writable"] is False
