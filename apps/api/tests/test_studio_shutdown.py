"""A stalled HTTP client must not prevent Studio's lifespan/lease cleanup."""

import socket
import sqlite3
import threading
import time

import pytest
import uvicorn
from furnace.runtime.lease import WorkspaceBusy, WorkspaceLease
from furnace_api import studio

TOKEN = "shutdown-regression-token-" * 2


def test_partial_request_cannot_hold_workspace_after_shutdown(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    servers = []
    errors = []
    real_server = uvicorn.Server

    def capture_server(config):
        server = real_server(config)
        servers.append(server)
        return server

    monkeypatch.setattr(uvicorn, "Server", capture_server)
    monkeypatch.setattr(studio.secrets, "token_urlsafe", lambda _: TOKEN)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    def run():
        try:
            studio.launch(workspace, port, open_browser=False)
        except (Exception, SystemExit) as error:
            errors.append(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    partial = None
    try:
        deadline = time.monotonic() + 10
        while not servers or not servers[0].started:
            assert not errors, errors
            assert time.monotonic() < deadline, "Studio did not start"
            time.sleep(0.01)
        with pytest.raises(WorkspaceBusy), WorkspaceLease(workspace):
            pytest.fail("Running Studio did not own its workspace")
        partial = socket.create_connection(("127.0.0.1", port), timeout=2)
        partial.sendall(
            (
                "POST /api/projects HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\nX-Furnace-Session: {TOKEN}\r\n"
                'Content-Type: application/json\r\nContent-Length: 1024\r\n\r\n{"name":"unfinished'
            ).encode()
        )
        partial.settimeout(0.2)
        with pytest.raises(socket.timeout):
            partial.recv(1)
        # The signal handler sets this same flag. Keep the client open throughout
        # shutdown: closing it first would hide the unbounded body-drain defect.
        servers[0].should_exit = True
        thread.join(timeout=8)
        assert not thread.is_alive(), "A stalled HTTP body prevented Studio shutdown"
        assert not errors, errors
        with WorkspaceLease(workspace), sqlite3.connect(workspace / "studio.sqlite3") as database:
            assert database.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.5)
    finally:
        if partial is not None:
            partial.close()
        if servers:
            servers[0].should_exit = True
            servers[0].force_exit = True
        thread.join(timeout=5)
