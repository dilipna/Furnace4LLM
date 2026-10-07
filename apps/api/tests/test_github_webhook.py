"""GitHub webhook: signature, event filtering, and a runner job for real PR changes."""

import asyncio
import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from furnace.settings import get_settings
from furnace_api.main import app

pytestmark = pytest.mark.db
SECRET = "whsec-test"


def _post(c, event, payload, secret=SECRET):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return c.post(
        "/api/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": sig,
            "content-type": "application/json",
        },
    )


def _pr(action="synchronize", head_repo="o/r", draft=False):
    return {
        "action": action,
        "repository": {"full_name": "o/r"},
        "pull_request": {
            "number": 7,
            "draft": draft,
            "head": {"sha": "a" * 40, "repo": {"full_name": head_repo}},
        },
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FURNACE_GITHUB_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_unconfigured_deployment_rejects_webhooks(monkeypatch):
    monkeypatch.delenv("FURNACE_GITHUB_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as c:
        assert _post(c, "ping", {}).status_code == 503
    get_settings.cache_clear()


def test_bad_signature_is_rejected(client):
    assert _post(client, "pull_request", _pr(), secret="wrong").status_code == 401


@pytest.mark.parametrize(
    ("event", "payload", "reason"),
    [
        ("ping", {"zen": "hi"}, "ping"),
        ("push", {"action": None}, "ignored push"),
        ("pull_request", _pr(action="closed"), "ignored pull_request/closed"),
        ("pull_request", _pr(head_repo="stranger/r"), "fork"),
        ("pull_request", _pr(draft=True), "draft"),
    ],
)
def test_events_that_do_not_queue(client, event, payload, reason):
    r = _post(client, event, payload)
    assert r.status_code == 202 and r.json()["queued"] is False and reason in r.json()["reason"]


def test_pull_request_change_enqueues_a_runner_job(client):
    r = _post(client, "pull_request", _pr())
    assert r.status_code == 202 and r.json()["queued"] is True
    job_id = uuid.UUID(r.json()["job_id"])

    async def fetch():
        from furnace.db.models import Job
        from furnace.db.session import session_scope

        async with session_scope() as s:
            return await s.get(Job, job_id)

    job = asyncio.run(fetch())
    assert job is not None and job.queue == "runner" and job.kind == "guard.pr"
    assert job.payload == {"repo": "o/r", "number": 7, "head_sha": "a" * 40}
