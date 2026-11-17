"""Real loopback HTTP transport, not model inference; no weights or serving framework."""

import contextlib
import io
import json
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from furnace.runtime.endpoint import LocalChatEndpoint, endpoint_port
from furnace.runtime.manager import RuntimeFault
from furnace_api.studio import create_app

TOKEN = "local-endpoint-transport-test-session-" * 2


@pytest.fixture
def server():
    class State:
        mode = "normal"

        def __init__(self):
            self.requests = []
            self.entered = threading.Event()
            self.release = threading.Event()

    state = State()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def reply(self, value, status=200):
            raw = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(raw)

        def do_GET(self):
            state.requests.append((self.path, None))
            if state.mode == "redirect":
                self.reply({}, 302)
            else:
                self.reply({"data": [{"id": "transport-test"}]})

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append((self.path, data))
            if state.mode == "hold":
                state.entered.set()
                state.release.wait(timeout=2)
            if state.mode == "error":
                return self.reply({"error": "PRIVATE UPSTREAM MESSAGE"}, 500)
            if state.mode == "slow":
                time.sleep(2)
            if state.mode == "oversized":
                return self.reply(b"x" * 70000)
            if state.mode == "malformed":
                return self.reply({"choices": []})
            if state.mode == "drip":
                raw = json.dumps({"model": "transport-test", "choices": []}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                try:
                    for char in raw:
                        self.wfile.write(bytes([char]))
                        self.wfile.flush()
                        time.sleep(0.05)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            self.reply(
                {
                    "model": "different" if state.mode == "mismatch" else "transport-test",
                    "choices": [
                        {
                            "message": {
                                "content": {
                                    "surrogate_high": "\ud800",
                                    "surrogate_low": "\udfff",
                                    "unicode": "answer \U0001f642",
                                }.get(state.mode, "answer")
                            },
                            "finish_reason": "length" if state.mode == "truncated" else "stop",
                        }
                    ],
                }
            )

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    config = {
        "base_url": f"http://127.0.0.1:{httpd.server_port}/v1",
        "model_id": "transport-test",
        "declared_revision": "test-server-not-a-model",
        "timeout_seconds": 1,
        "max_tokens": 16,
    }
    try:
        yield state, config
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/v1",
        "http://127.0.0.2:8000/v1",
        "https://127.0.0.1:8000/v1",
        "http://127.0.0.1:80/v1",
        "http://127.0.0.1:8000/v1?token=secret",
        "http://user:secret@127.0.0.1:8000/v1",
        "http://127.0.0.1:8000/v1#fragment",
        "http://2130706433:8000/v1",
        "http://[::1]:8000/v1",
        "http://example.com:8000/v1",
        "http://127.0.0.1:8000/other",
        "http://127.0.0.1:bad/v1",
        " http://127.0.0.1:8000/v1",
        "http://127.0.0.1:8000/v1\n",
    ],
)
def test_only_literal_loopback_port_and_fixed_base_path(url):
    with pytest.raises(RuntimeFault):
        endpoint_port(url)


def test_transport_ignores_proxies_and_never_follows_redirects(server, monkeypatch):
    state, config = server
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    LocalChatEndpoint().check(config)
    state.mode = "redirect"
    with pytest.raises(RuntimeFault, match="endpoint_http_302"):
        LocalChatEndpoint().check(config)
    assert len(state.requests) == 2


@pytest.mark.parametrize(
    "mode", ["error", "malformed", "oversized", "mismatch", "surrogate_high", "surrogate_low"]
)
def test_bad_responses_cannot_become_success_or_leak_upstream_errors(server, mode):
    state, config = server
    state.mode = mode
    with pytest.raises(RuntimeFault) as failure:
        LocalChatEndpoint().predict(config, "sanitized input", 1)
    assert "PRIVATE" not in str(failure.value)


def test_valid_non_bmp_output_is_preserved(server):
    state, config = server
    state.mode = "unicode"
    result = LocalChatEndpoint().predict(config, "bounded", 1)
    assert result["output"] == "answer \U0001f642"
    assert len(state.requests) == 1


@pytest.mark.parametrize("mode", ["slow", "drip"])
def test_wall_clock_deadline_covers_slow_and_trickling_bodies(server, mode):
    state, config = server
    state.mode = mode
    started = time.monotonic()
    with pytest.raises(RuntimeFault):
        LocalChatEndpoint().predict(config, "bounded", 0.25)
    assert time.monotonic() - started < 1.25


def configure(client, pid, config):
    response = client.put(f"/api/projects/{pid}/model/connection", json=config)
    assert response.status_code == 200, response.text
    return response.json()


def connect(client, pid):
    response = client.post(f"/api/projects/{pid}/model/connect", json={"consent": True})
    assert response.status_code == 200, response.text


def add_cases(client, pid):
    assert (
        client.put(
            f"/api/projects/{pid}/cases",
            json={
                "cases": [
                    {
                        "name": "Exact",
                        "input": "first",
                        "expected_behavior": "synthetic protocol check",
                        "expected_output": "answer",
                    },
                    {
                        "name": "Descriptive",
                        "input": "second",
                        "expected_behavior": "needs human scoring",
                    },
                ]
            },
        ).status_code
        == 200
    )


@pytest.mark.parametrize("mode", ["surrogate_high", "surrogate_low"])
def test_invalid_unicode_interrupts_persisted_run_and_requires_explicit_retry(
    tmp_path, server, mode
):
    state, config = server
    with TestClient(
        create_app(tmp_path, TOKEN),
        base_url="http://localhost",
        headers={"x-furnace-session": TOKEN},
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configure(client, pid, config)
        connect(client, pid)
        state.mode = mode
        response = client.post(f"/api/projects/{pid}/model/evaluate")
        assert response.status_code == 200
        saved = client.get(f"/api/projects/{pid}/model").json()["model_endpoint"]
        assert saved["state"]["status"] == "failed"
        assert saved["evaluation"]["status"] == "interrupted"
        assert saved["evaluation"]["results"] == [
            {
                "case_index": 0,
                "status": "error",
                "reason": "endpoint_invalid_or_mismatched_completion",
            }
        ]
        assert len(state.requests) == 2  # Readiness plus one completion; second case never ran.
        assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409
        assert len(state.requests) == 2
        state.mode = "normal"
        connect(client, pid)
        retried = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"]
        assert len(state.requests) == 5  # Reconnect and both cases really execute.
        assert [run["status"] for run in retried["history"]] == ["interrupted", "completed"]
        assert [result["status"] for result in retried["evaluation"]["results"]] == [
            "exact_pass",
            "unscored",
        ]


def test_actual_requests_state_identity_export_and_failure_then_explicit_retry(tmp_path, server):
    state, config = server
    app = create_app(tmp_path, TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configured = configure(client, pid, config)
        assert state.requests == []  # Saving is not execution.
        refused = client.post(f"/api/projects/{pid}/model/connect", json={"consent": False})
        assert refused.status_code == 409
        assert refused.json()["detail"] == "explicit_local_endpoint_consent_required"
        assert state.requests == []
        connect(client, pid)
        assert state.requests == [("/v1/models", None)]  # Readiness is not inference.
        response = client.post(f"/api/projects/{pid}/model/predict", json={"input": "first"})
        assert response.json()["output"] == "answer"
        assert state.requests[-1][1]["messages"] == [{"role": "user", "content": "first"}]
        assert state.requests[-1][1]["stream"] is False
        assert state.requests[-1][1]["max_tokens"] == 16
        state.mode = "error"
        failed = client.post(f"/api/projects/{pid}/model/evaluate").json()
        failed_run_id = failed["model_endpoint"]["evaluation"]["run_id"]
        assert failed["model_endpoint"]["evaluation"]["status"] == "interrupted"
        assert len(failed["model_endpoint"]["evaluation"]["results"]) == 1
        assert failed["model_endpoint"]["evaluation"]["results"][0]["status"] == "error"
        assert failed["model_endpoint"]["state"]["status"] == "failed"
        requests_after_failure = len(state.requests)
        assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409
        assert len(state.requests) == requests_after_failure  # No hidden retries.
        state.mode = "normal"
        connect(client, pid)
        completed = client.post(f"/api/projects/{pid}/model/evaluate").json()
        endpoint = completed["model_endpoint"]
        assert failed_run_id in json.dumps(completed), "Retry erased the failed attempt"
        assert [run["status"] for run in endpoint["history"]] == ["interrupted", "completed"]
        assert endpoint["history"][0]["run_id"] == failed_run_id
        assert all(run["matches_current_configuration"] for run in endpoint["history"])
        assert all(run["case_count"] == 2 for run in endpoint["history"])
        assert "answer" not in json.dumps(endpoint["history"])
        assert len(state.requests) == requests_after_failure + 3  # Check + two actual completions.
        assert [r["status"] for r in endpoint["evaluation"]["results"]] == [
            "exact_pass",
            "unscored",
        ]
        assert completed["evaluation"] is None  # Endpoint results never become fixture evidence.
        assert not endpoint["model_identity_independently_verified"]
        assert "answer" not in json.dumps(completed["events"])
        with zipfile.ZipFile(
            io.BytesIO(client.post(f"/api/projects/{pid}/kit").content)
        ) as archive:
            exported = json.loads(archive.read("workspace-plan.json"))["model_endpoint"]
            assert exported["configuration_sha256"] == endpoint["configuration_sha256"]
            assert exported["evaluation"]["project_id"] == pid
            assert exported["evaluation"]["execution_kind"] == "local_endpoint_response"
            assert exported["history"] == endpoint["history"]
        changed = client.put(f"/api/projects/{pid}/contract", json={"notes": "changed"}).json()
        assert changed["model_endpoint"]["verification"] == "no_current_endpoint_evidence"
        assert len(changed["model_endpoint"]["history"]) == 2
        assert not any(
            run["matches_current_configuration"] for run in changed["model_endpoint"]["history"]
        )
        assert (
            changed["model_endpoint"]["configuration_sha256"]
            != configured["model_endpoint"]["configuration_sha256"]
        )
        assert (
            client.post(f"/api/projects/{pid}/model/predict", json={"input": "x"}).status_code
            == 409
        )
        assert client.get("/model").status_code == 200
        assert "javascript" in client.get("/assets/model.js").headers["content-type"]


def test_truncation_is_incomplete_even_when_exact_text_matches(tmp_path, server):
    state, config = server
    with TestClient(
        create_app(tmp_path, TOKEN),
        base_url="http://localhost",
        headers={"x-furnace-session": TOKEN},
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configure(client, pid, config)
        connect(client, pid)
        state.mode = "truncated"
        p = client.post(f"/api/projects/{pid}/model/evaluate").json()
        assert [r["status"] for r in p["model_endpoint"]["evaluation"]["results"]] == [
            "incomplete",
            "incomplete",
        ]


def test_restart_does_not_reconnect_or_rerun_and_preserves_saved_evidence(tmp_path, server):
    state, config = server
    args = {"base_url": "http://localhost", "headers": {"x-furnace-session": TOKEN}}
    with TestClient(create_app(tmp_path, TOKEN), **args) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configure(client, pid, config)
        connect(client, pid)
        p = client.post(f"/api/projects/{pid}/model/evaluate").json()
        run_id = p["model_endpoint"]["evaluation"]["run_id"]
    before = len(state.requests)
    with TestClient(create_app(tmp_path, TOKEN), **args) as client:
        restored = client.get(f"/api/projects/{pid}/model").json()
        assert restored["model_endpoint"]["state"]["status"] == "disconnected"
        assert restored["model_endpoint"]["evaluation"]["run_id"] == run_id
        assert restored["model_endpoint"]["history"][-1]["run_id"] == run_id
        assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409
        assert len(state.requests) == before
        connect(client, pid)  # Disconnect never stopped our independent HTTP server.


def test_session_validation_and_bad_configs_never_issue_network_requests(tmp_path, server):
    state, config = server
    with TestClient(
        create_app(tmp_path, TOKEN),
        base_url="http://localhost",
        headers={"x-furnace-session": TOKEN},
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        path = f"/api/projects/{pid}/model/connection"
        assert (
            client.put(path, json=config, headers={"x-furnace-session": "wrong"}).status_code == 401
        )
        assert (
            client.put(path, json=config, headers={"Origin": "http://evil.invalid"}).status_code
            == 403
        )
        assert client.put(path, json={**config, "api_key": "never-store"}).status_code == 422
        assert (
            client.put(
                path, json={**config, "base_url": "http://remote.invalid:8000/v1"}
            ).status_code
            == 422
        )
        assert client.put(path, json={**config, "declared_revision": " "}).status_code == 422
        assert state.requests == []


def test_disconnect_during_request_stops_batch_and_retry_reexecutes(tmp_path, server):
    state, config = server
    app = create_app(tmp_path, TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configure(client, pid, config)
        connect(client, pid)
        state.mode = "hold"
        replies = []
        worker = threading.Thread(
            target=lambda: replies.append(client.post(f"/api/projects/{pid}/model/evaluate"))
        )
        worker.start()
        assert state.entered.wait(timeout=2)
        disconnected = []
        stopper = threading.Thread(
            target=lambda: disconnected.append(client.post(f"/api/projects/{pid}/model/disconnect"))
        )
        stopper.start()
        deadline = time.monotonic() + 2
        while not app.state.model.flag(pid).is_set() and time.monotonic() < deadline:
            threading.Event().wait(0.01)
        assert app.state.model.flag(pid).is_set()
        state.release.set()
        worker.join(timeout=3)
        stopper.join(timeout=3)
        assert not worker.is_alive()
        assert not stopper.is_alive()
        assert disconnected[0].json()["model_endpoint"]["state"]["status"] == "disconnected"
        result = replies[0].json()["model_endpoint"]["evaluation"]
        assert result["status"] == "interrupted"
        assert [r["status"] for r in result["results"]] == ["error"]
        assert len(state.requests) == 2  # One readiness check, one completion; no second case.
        assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409
        assert len(state.requests) == 2
        state.mode = "normal"
        connect(client, pid)
        retried = client.post(f"/api/projects/{pid}/model/evaluate").json()
        assert retried["model_endpoint"]["evaluation"]["status"] == "completed"
        assert len(state.requests) == 5  # Recheck + both cases execute again.


def test_shutdown_recovery_never_rewrites_a_batch_that_ended_while_it_waited(tmp_path, server):
    # Recovery used to read every project before taking its lock. A batch finishing in
    # the meantime was then overwritten by that stale "running" copy as interrupted,
    # silently dropping recorded cases from the current result and from history.
    state, config = server
    app = create_app(tmp_path, TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configure(client, pid, {**config, "timeout_seconds": 3})
        connect(client, pid)
        state.mode = "hold"
        replies = []
        worker = threading.Thread(
            target=lambda: replies.append(client.post(f"/api/projects/{pid}/model/evaluate"))
        )
        worker.start()
        assert state.entered.wait(timeout=2)
        recovering = threading.Thread(target=app.state.model.recover)
        recovering.start()
        threading.Event().wait(0.2)  # recovery is now waiting for the project lock
        state.release.set()
        worker.join(timeout=5)
        recovering.join(timeout=5)
        assert not worker.is_alive()
        assert not recovering.is_alive()
        returned = replies[0].json()["model_endpoint"]["evaluation"]
        saved = client.get(f"/api/projects/{pid}/model").json()["model_endpoint"]
        assert saved["evaluation"]["status"] == returned["status"]
        assert saved["evaluation"]["results"] == returned["results"]
        retained = [run for run in saved["history"] if run["run_id"] == returned["run_id"]]
        assert retained[0]["results"] == returned["results"]
        assert saved["state"]["status"] == "disconnected"


def test_restart_retains_partial_run_without_reusing_it_for_another_project(tmp_path, server):
    state, config = server
    args = {"base_url": "http://localhost", "headers": {"x-furnace-session": TOKEN}}
    app = create_app(tmp_path, TOKEN)
    with TestClient(app, **args) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configure(client, pid, config)
        connect(client, pid)
        p = client.post(f"/api/projects/{pid}/model/evaluate").json()
        run = p["model_endpoint"]["evaluation"]
        partial = {**run, "status": "running", "results": run["results"][:1]}
        app.state.model.store.change(
            pid, "model_evaluation", partial, "Simulated process interruption"
        )
    before = len(state.requests)
    with TestClient(create_app(tmp_path, TOKEN), **args) as client:
        endpoint = client.get(f"/api/projects/{pid}/model").json()["model_endpoint"]
        assert endpoint["evaluation"]["status"] == "interrupted"
        assert endpoint["history"][-1]["status"] == "interrupted"
        assert len(endpoint["evaluation"]["results"]) == 1
        assert len(state.requests) == before
        assert client.post(f"/api/projects/{pid}/model/evaluate").status_code == 409
        # A result copied between project records cannot attest to the receiving project.
        from furnace_api.studio_model_evidence import view

        stored = client.get(f"/api/projects/{pid}/model").json()
        assert view({**stored, "id": "a" * 32, "model_evaluation": run})["verification"] == (
            "no_current_endpoint_evidence"
        )
        changed = configure(client, pid, {**config, "declared_revision": "different-revision"})
        assert changed["model_endpoint"]["evaluation"] is None
        assert changed["model_endpoint"]["history"][-1]["run_id"] == run["run_id"]
        assert changed["model_endpoint"]["configuration_sha256"] != run["configuration_sha256"]
        assert len(state.requests) == before


def test_history_retention_is_chronological_for_failures_and_successes(tmp_path, server):
    state, config = server
    args = {"base_url": "http://localhost", "headers": {"x-furnace-session": TOKEN}}
    ids, statuses = [], []
    with TestClient(create_app(tmp_path, TOKEN), **args) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        endpoint = configure(client, pid, config)["model_endpoint"]
        for index in range(12):
            connect(client, pid)
            state.mode = "error" if index % 3 == 0 else "normal"
            endpoint = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"]
            ids.append(endpoint["evaluation"]["run_id"])
            statuses.append(endpoint["evaluation"]["status"])
        assert len(state.requests) == 32  # 12 readiness checks; 8*2 + 4*1 completions.
        assert endpoint["history_limit"] == 10
        assert [run["run_id"] for run in endpoint["history"]] == ids[-10:]
        assert [run["status"] for run in endpoint["history"]] == statuses[-10:]
        assert len(set(ids)) == 12
        before = len(state.requests)
    with TestClient(create_app(tmp_path, TOKEN), **args) as client:
        restored = client.get(f"/api/projects/{pid}/model").json()["model_endpoint"]
        assert [run["run_id"] for run in restored["history"]] == ids[-10:]
        assert len(state.requests) == before  # Reading history never re-executes a case.
        with zipfile.ZipFile(
            io.BytesIO(client.post(f"/api/projects/{pid}/kit").content)
        ) as archive:
            exported = json.loads(archive.read("workspace-plan.json"))["model_endpoint"]
            assert exported["history"] == restored["history"]


def test_legacy_last_result_survives_reconfiguration_and_cannot_attest_another_project(
    tmp_path, server
):
    from furnace_api.studio_model_evidence import view

    state, config = server
    app = create_app(tmp_path, TOKEN)
    with TestClient(
        app, base_url="http://localhost", headers={"x-furnace-session": TOKEN}
    ) as client:
        pid = client.post("/api/examples/framework").json()["id"]
        add_cases(client, pid)
        configure(client, pid, config)
        connect(client, pid)
        endpoint = client.post(f"/api/projects/{pid}/model/evaluate").json()["model_endpoint"]
        old = dict(endpoint["evaluation"])
        old.pop("case_count")
        old.pop("model_id")
        # Earlier previews stored only this single result, without a history field.
        with app.state.model.store.connect() as db:
            project = json.loads(
                db.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()[0]
            )
            project.pop("model_evaluation_history")
            project["model_evaluation"] = old
            db.execute("UPDATE projects SET data=? WHERE id=?", (json.dumps(project), pid))
        before = len(state.requests)
        changed = configure(client, pid, {**config, "declared_revision": "new-declaration"})
        history = changed["model_endpoint"]["history"]
        assert len(history) == 1 and history[0]["run_id"] == old["run_id"]
        assert "case_count" not in history[0]
        assert not history[0]["matches_current_configuration"]
        assert changed["model_endpoint"]["evaluation"] is None
        assert len(state.requests) == before
        assert view({**changed, "id": "b" * 32})["history"] == []
        restored_config = configure(client, pid, config)["model_endpoint"]
        assert restored_config["history"][0]["matches_current_configuration"]
        assert restored_config["evaluation"] is None
        assert restored_config["verification"] == "no_current_endpoint_evidence"
        assert (
            client.post(f"/api/projects/{pid}/model/predict", json={"input": "x"}).status_code
            == 409
        )
        assert len(state.requests) == before
