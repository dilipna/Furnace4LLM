"""GitHub App setup (manifest flow) and pull-mode webhooks (delivery log poller)."""

import json
import socket
import threading
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from furnace.github import deliveries, setup
from furnace.github.client import GitHubApp

KEY = (
    rsa.generate_private_key(public_exponent=65537, key_size=2048)
    .private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    .decode()
)


@pytest.mark.adversarial
def test_manifest_requests_exactly_the_least_privilege_set():
    m = setup.manifest(
        name="furnace-dev", homepage="https://x", webhook_url="https://h", redirect_url="http://r"
    )
    assert m["default_permissions"] == {
        "contents": "write",
        "pull_requests": "write",
        "checks": "write",
        "metadata": "read",
    }
    assert m["default_events"] == ["pull_request"] and m["public"] is False
    assert m["hook_attributes"] == {"url": "https://h", "active": True}


def test_form_page_escapes_the_manifest():
    m = json.dumps({"name": "x' onmouseover='alert(1)", "url": "<script>"})
    page = setup.form_page(m, "https://github.com/settings/apps/new?state=s")
    assert "x' onmouseover" not in page and '<script>"' not in page
    assert "&#x27;" in page


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.adversarial
def test_callback_requires_the_state_it_issued():
    port = _free_port()
    got: dict = {}
    t = threading.Thread(
        target=lambda: got.update(code=setup.wait_for_code("PAGE", "good-state", port, 20))
    )
    t.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            assert httpx.get(base + "/").text == "PAGE"
            break
        except httpx.ConnectError:
            threading.Event().wait(0.1)
    assert (
        httpx.get(base + "/callback", params={"code": "c1", "state": "forged"}).status_code == 400
    )
    assert (
        httpx.get(base + "/callback", params={"code": "c2", "state": "good-state"}).status_code
        == 200
    )
    t.join(10)
    assert got == {"code": "c2"}


@pytest.mark.adversarial
async def test_conversion_writes_key_and_env_without_printing_secrets(
    tmp_path, monkeypatch, capsys
):
    def gh(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST" and req.url.path == "/app-manifests/one-time/conversions"
        return httpx.Response(
            201,
            json={
                "id": 4321,
                "slug": "furnace-dev",
                "html_url": "https://github.com/apps/furnace-dev",
                "pem": "-----BEGIN RSA PRIVATE KEY-----\nSECRETKEY\n-----END RSA PRIVATE KEY-----\n",
                "webhook_secret": "whsec-SECRET",
                "client_secret": "cs-SECRET",
            },
        )

    created = await setup.convert("one-time", transport=httpx.MockTransport(gh))
    env = tmp_path / ".env"
    env.write_text("FURNACE_ENV=dev\nFURNACE_GITHUB_APP_ID=old\n# keep me\n", encoding="utf-8")
    key = setup.write_credentials(created, tmp_path / "keys", env)
    assert key.read_text(encoding="utf-8").startswith("-----BEGIN RSA PRIVATE KEY-----")
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines[:3] == ["FURNACE_ENV=dev", "FURNACE_GITHUB_APP_ID=4321", "# keep me"]
    assert f"FURNACE_GITHUB_PRIVATE_KEY_PATH={key.resolve().as_posix()}" in lines
    assert "FURNACE_GITHUB_WEBHOOK_SECRET=whsec-SECRET" in lines
    assert not any("cs-SECRET" in line for line in lines)  # the OAuth secret is not kept

    # the whole command: its printed output names files, never secrets
    async def fake_convert(code, transport=None):
        return created

    monkeypatch.setattr(setup, "wait_for_code", lambda page, state, port: "one-time")
    monkeypatch.setattr(setup, "convert", fake_convert)
    out = await _in_thread(
        lambda: setup.run_setup(
            name="furnace-dev", webhook_url="https://h", org=None, port=1,
            key_dir=tmp_path / "keys", env_file=env, open_browser=False,
        )
    )  # fmt: skip
    printed = capsys.readouterr().out + json.dumps(out)
    assert "SECRET" not in printed and out["app_id"] == "4321"
    assert out["next"].endswith("/installations/new")


async def _in_thread(fn):
    import asyncio

    return await asyncio.to_thread(fn)


# ------------------------------------------------------------------ delivery log poller


def _now(delta_s=0):
    return (datetime.now(UTC) + timedelta(seconds=delta_s)).isoformat().replace("+00:00", "Z")


def _pr_payload(sha="d" * 40):
    return {
        "action": "opened",
        "repository": {"full_name": "o/r"},
        "installation": {"id": 9},
        "pull_request": {
            "number": 2,
            "draft": False,
            "head": {"sha": sha, "repo": {"full_name": "o/r"}},
        },
    }


class FakeAppAPI:
    def __init__(self, items, payloads):
        self.items, self.payloads, self.fetched = items, payloads, []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"].startswith("Bearer ey")  # App JWT, not a token
        if req.url.path == "/app/hook/deliveries":
            return httpx.Response(200, json=self.items)
        did = int(req.url.path.rsplit("/", 1)[1])
        self.fetched.append(did)
        return httpx.Response(200, json={"request": {"payload": self.payloads[did]}})


@pytest.mark.db
async def test_poller_enqueues_new_deliveries_once_and_skips_old_history(clean_jobs):
    from furnace.db.models import Job, WebhookDelivery
    from furnace.db.session import session_scope
    from sqlalchemy import select, text

    async with session_scope() as s:
        await s.execute(text("TRUNCATE webhook_deliveries"))
    items = [  # newest first, as GitHub lists them
        {"id": 3, "guid": "g-new", "event": "pull_request", "action": "opened",
         "delivered_at": _now(-5), "redelivery": True},
        {"id": 2, "guid": "g-new", "event": "pull_request", "action": "opened",
         "delivered_at": _now(-30), "redelivery": False},
        {"id": 1, "guid": "g-old", "event": "pull_request", "action": "opened",
         "delivered_at": _now(-7200), "redelivery": False},
    ]  # fmt: skip
    api = FakeAppAPI(items, {1: _pr_payload("e" * 40), 2: _pr_payload(), 3: _pr_payload()})
    app = GitHubApp("1", KEY, transport=httpx.MockTransport(api))
    seen: list[dict] = []
    await deliveries.run(app, once=True, lookback=timedelta(minutes=10), on_result=seen.append)
    await deliveries.run(app, once=True, lookback=timedelta(minutes=10), on_result=seen.append)
    assert [r["guid"] for r in seen] == ["g-new"] and seen[0]["queued"] is True
    assert len(api.fetched) == 1  # the redelivery (same GUID) and old history not fetched
    async with session_scope() as s:
        jobs = list((await s.execute(select(Job))).scalars())
        rows = list((await s.execute(select(WebhookDelivery))).scalars())
    assert len(jobs) == 1 and jobs[0].payload["head_sha"] == "d" * 40
    assert [(r.delivery_id, r.source, r.outcome) for r in rows] == [("g-new", "poll", "queued")]


async def test_poller_reports_a_malformed_delivery_once():
    items = [{"id": 5, "guid": "g-bad", "event": "pull_request", "delivered_at": _now(-1)}]

    class Log:
        async def recent(self):
            return items

        async def payload(self, did):
            return {"action": "opened"}  # no pull_request object

    calls: list = []

    async def ingest(guid, event, payload):
        from furnace.github.events import InvalidEvent

        calls.append(guid)
        raise InvalidEvent("pull_request event missing 'pull_request'")

    async def known(guids):
        return set()

    rejected: set[str] = set()
    since = datetime.now(UTC) - timedelta(minutes=1)
    first = await deliveries.poll_once(Log(), ingest, known, since, rejected)  # type: ignore[arg-type]
    second = await deliveries.poll_once(Log(), ingest, known, since, rejected)  # type: ignore[arg-type]
    assert first[0]["queued"] is False and "rejected" in first[0]["reason"]
    assert second == [] and calls == ["g-bad"]
