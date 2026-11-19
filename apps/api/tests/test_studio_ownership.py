"""Startup must own a workspace before opening or initializing its database."""

import sqlite3

import pytest
from fastapi.testclient import TestClient
from furnace.runtime.lease import WorkspaceBusy, WorkspaceLease
from furnace_api.studio import create_app

TOKEN = "startup-ownership-test-token-" * 2


def test_busy_new_workspace_is_not_initialized_by_a_rejected_application(tmp_path):
    workspace = tmp_path / "workspace"
    with WorkspaceLease(workspace):
        app = create_app(workspace, TOKEN)
        assert not (workspace / "studio.sqlite3").exists()
        with pytest.raises(WorkspaceBusy), TestClient(app):
            pytest.fail("A second application acquired the workspace")
        assert not (workspace / "studio.sqlite3").exists()
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        assert client.get("/api/projects").json() == []
        assert (workspace / "studio.sqlite3").is_file()


def test_busy_workspace_database_is_not_even_opened_before_ownership(tmp_path):
    workspace = tmp_path / "workspace"
    with WorkspaceLease(workspace):
        database = workspace / "studio.sqlite3"
        database.write_bytes(b"incomplete owner-controlled database")
        original = database.read_bytes()
        app = create_app(workspace, TOKEN)
        with pytest.raises(WorkspaceBusy), TestClient(app):
            pytest.fail("A second application acquired the workspace")
        assert database.read_bytes() == original


def test_initialization_failure_releases_lease_and_preserves_database(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = workspace / "studio.sqlite3"
    database.write_bytes(b"invalid database; do not replace")
    original = database.read_bytes()
    app = create_app(workspace, TOKEN)
    with pytest.raises(sqlite3.DatabaseError), TestClient(app):
        pytest.fail("Invalid database was silently accepted")
    assert database.read_bytes() == original
    with WorkspaceLease(workspace):
        pass
