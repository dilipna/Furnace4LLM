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


def _post(c, event, payload, secret=SECRET, delivery=None, raw=None):
    body = raw if raw is not None else json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": sig,
        "content-type": "application/json",
    }
    if delivery is not False:
        headers["X-GitHub-Delivery"] = delivery or str(uuid.uuid4())
    return c.post("/api/github/webhook", content=body, headers=headers)


def _pr(action="synchronize", head_repo="o/r", draft=False, sha="a" * 40, repo="o/r"):
    return {
        "action": action,
        "repository": {"full_name": repo},
        "installation": {"id": 4242},
        "pull_request": {
            "number": 7,
            "draft": draft,
            "head": {"sha": sha, "repo": {"full_name": head_repo}},
        },
    }


@pytest.fixture
def client(monkeypatch):
    asyncio.run(_truncate())
    monkeypatch.setenv("FURNACE_GITHUB_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


async def _truncate():
    from furnace.db.session import session_scope
    from sqlalchemy import text

    async with session_scope() as s:
        await s.execute(text("TRUNCATE jobs, webhook_deliveries CASCADE"))


def _rows(sql, **params):
    async def go():
        from furnace.db.session import session_scope
        from sqlalchemy import text

        async with session_scope() as s:
            return [tuple(r) for r in (await s.execute(text(sql), params)).all()]

    return asyncio.run(go())


def test_unconfigured_deployment_rejects_webhooks(monkeypatch):
    monkeypatch.delenv("FURNACE_GITHUB_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as c:
        assert _post(c, "ping", {}).status_code == 503
    get_settings.cache_clear()


@pytest.mark.adversarial
def test_bad_signature_is_rejected(client):
    assert _post(client, "pull_request", _pr(), secret="wrong").status_code == 401


@pytest.mark.adversarial
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
    assert job.payload["repo"] == "o/r" and job.payload["number"] == 7
    assert job.payload["head_sha"] == "a" * 40 and job.payload["installation_id"] == 4242
    assert job.dedupe_key == f"guard.pr:o/r#7@{'a' * 40}" and job.timeout_s == 1800


@pytest.mark.adversarial
def test_a_replayed_delivery_is_a_no_op(client):
    """Same GUID (a GitHub redelivery, or a captured signed request replayed): one job."""
    first = _post(client, "pull_request", _pr(), delivery="d-1")
    again = _post(client, "pull_request", _pr(), delivery="d-1")
    assert first.json()["queued"] is True
    assert again.status_code == 202 and again.json()["duplicate"] is True
    assert _rows("SELECT count(*) FROM jobs") == [(1,)]


def test_two_events_for_the_same_head_commit_share_one_job(client):
    a = _post(client, "pull_request", _pr(action="opened"))
    b = _post(client, "pull_request", _pr(action="ready_for_review"))
    assert a.json()["queued"] is True and b.json()["queued"] is False
    assert b.json()["job_id"] == a.json()["job_id"] and "attached" in b.json()["reason"]
    c = _post(client, "pull_request", _pr(sha="b" * 40))  # a new push: a new job
    assert c.json()["queued"] is True and c.json()["job_id"] != a.json()["job_id"]


def test_every_delivery_leaves_an_audit_row(client):
    _post(client, "pull_request", _pr(), delivery="d-audit-1")
    _post(client, "pull_request", _pr(head_repo="stranger/r"), delivery="d-audit-2")
    rows = _rows(
        "SELECT delivery_id, event, action, repo, installation_id, outcome, job_id IS NOT NULL "
        "FROM webhook_deliveries ORDER BY delivery_id"
    )
    assert rows == [
        ("d-audit-1", "pull_request", "synchronize", "o/r", 4242, "queued", True),
        ("d-audit-2", "pull_request", "synchronize", "o/r", 4242, "ignored", False),
    ]


@pytest.mark.parametrize(
    ("raw", "payload", "delivery", "status"),
    [
        (b"not json", None, None, 400),
        (None, {"action": "opened"}, None, 400),  # pull_request without the PR
        (None, _pr(sha="zz"), None, 400),  # not a commit id
        (None, _pr(repo="../../etc"), None, 400),  # not owner/name
        (None, _pr(), False, 400),  # no X-GitHub-Delivery
        (None, _pr(), "bad id; drop table", 400),
    ],
)
def test_malformed_signed_events_are_rejected_without_side_effects(
    client, raw, payload, delivery, status
):
    r = _post(client, "pull_request", payload, raw=raw, delivery=delivery)
    assert r.status_code == status
    assert _rows("SELECT count(*) FROM jobs") == [(0,)]
    assert _rows("SELECT count(*) FROM webhook_deliveries") == [(0,)]


@pytest.mark.adversarial
def test_repositories_outside_the_allowlist_are_ignored(client, monkeypatch):
    monkeypatch.setenv("FURNACE_GITHUB_ALLOWED_REPOS", "o/other, o/third")
    get_settings.cache_clear()
    r = _post(client, "pull_request", _pr())
    assert r.json()["queued"] is False and "ALLOWED_REPOS" in r.json()["reason"]
    monkeypatch.setenv("FURNACE_GITHUB_ALLOWED_REPOS", "O/R")
    get_settings.cache_clear()
    assert _post(client, "pull_request", _pr()).json()["queued"] is True


@pytest.mark.adversarial
def test_oversized_bodies_are_refused_before_parsing(client):
    r = _post(client, "pull_request", None, raw=b"{" + b" " * (5 * 1024 * 1024 + 1) + b"}")
    assert r.status_code == 413
