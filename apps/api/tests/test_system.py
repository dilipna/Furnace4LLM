import pytest
from fastapi.testclient import TestClient
from furnace_api.main import app

pytestmark = pytest.mark.db


def test_healthz():
    with TestClient(app) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["db"] is True
