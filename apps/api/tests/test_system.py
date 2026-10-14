import pytest
from fastapi.testclient import TestClient
from furnace_api.main import app

pytestmark = pytest.mark.db


def test_healthz():
    with TestClient(app) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["db"] is True


def test_hosted_runner_list_hides_host_details(monkeypatch):
    from furnace.settings import get_settings

    monkeypatch.setattr(get_settings(), "env", "prod")
    with TestClient(app) as c:
        rows = c.get("/api/runners").json()
    for r in rows:
        assert r["id"].startswith("runner-")
        assert set(r["capabilities"]) <= {"gpu", "docker"}
