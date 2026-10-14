"""The test session never sees the developer's GitHub App configuration or real GitHub."""

import os

import httpx
import pytest
from furnace.settings import Settings


def test_settings_ignore_the_developers_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "FURNACE_GITHUB_APP_ID=12345\nFURNACE_GITHUB_WEBHOOK_SECRET=real\n"
        "FURNACE_GITHUB_ALLOWED_REPOS=me/repo\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert s.github_app_id is None
    assert s.github_webhook_secret is None
    assert s.github_allowed_repos is None
    assert not [k for k in os.environ if k.startswith(("FURNACE_GITHUB_", "FURNACE_GUARD_"))]


@pytest.mark.parametrize("url", ["https://api.github.com/app", "https://smee.io/new"])
def test_real_github_and_smee_are_unreachable(url):
    with pytest.raises(RuntimeError, match="must not contact"):
        httpx.get(url, timeout=5)


async def test_real_github_is_unreachable_async():
    async with httpx.AsyncClient() as c:
        with pytest.raises(RuntimeError, match="must not contact"):
            await c.get("https://api.github.com/app")


def test_mock_transports_still_work():
    t = httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))
    with httpx.Client(transport=t) as c:
        assert c.get("https://api.github.com/app").json() == {"ok": True}
