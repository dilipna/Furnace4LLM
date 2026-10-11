"""Adversarial regressions not covered elsewhere: a scoped installation token must never
leave the process in anything Furnace stores or shows (job results, progress lines that
become job events, check-run text, error messages), even when GitHub echoes it back."""

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from furnace.github import flows
from furnace.github.client import GitHubApp, GitHubError
from furnace.guardian.execute import ItemResult
from furnace.guardian.impact import SuiteItem

pytestmark = pytest.mark.adversarial

TOKEN = "ghs_" + "S3cr3tT0kenValue" * 3
KEY = (
    rsa.generate_private_key(public_exponent=65537, key_size=2048)
    .private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    .decode()
)
SUITE = [SuiteItem("unit:tests/test_x.py", "unit", ["component:*"], {"code"}, always=True)]


class EchoingGitHub:
    """A GitHub that misbehaves: its error bodies echo the Authorization header back."""

    def __init__(self, fail_patch: bool = False):
        self.fail_patch = fail_patch
        self.bodies: list[str] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if req.content:
            self.bodies.append(req.content.decode())
        if p == "/repos/o/r/installation":
            return httpx.Response(200, json={"id": 77})
        if p == "/app/installations/77/access_tokens":
            return httpx.Response(201, json={"token": TOKEN})
        if p == "/repos/o/r/pulls/5":
            return httpx.Response(
                200,
                json={
                    "number": 5,
                    "title": "t",
                    "base": {"ref": "main", "sha": "b" * 40},
                    "head": {"ref": "f", "sha": "h" * 40, "repo": {"full_name": "o/r"}},
                },
            )
        if p.endswith("/check-runs") and req.method == "GET":
            return httpx.Response(200, json={"check_runs": []})
        if p == "/repos/o/r/check-runs" and req.method == "POST":
            return httpx.Response(201, json={"id": 1})
        if p == "/repos/o/r/check-runs/1" and self.fail_patch:
            echoed = req.headers.get("authorization", "")
            return httpx.Response(500, json={"message": f"internal error for {echoed}"})
        return httpx.Response(200, json={})


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    async def fetch(full_name, sha, token, dest):
        dest.mkdir(parents=True)
        (dest / "app.py").write_text("x = 1\n" if sha.startswith("b") else "x = 2\n")
        return dest

    monkeypatch.setattr(flows, "fetch_revision", fetch)
    monkeypatch.setattr(flows, "prepare", lambda b, h: (tmp_path / "w", b, h))
    monkeypatch.setattr(
        flows,
        "run_items",
        lambda items, ctx, progress, on_event=None: [ItemResult(items[0].key, "fail", "1 failed")],
    )
    return monkeypatch


async def test_token_never_appears_in_results_progress_or_check_text(stubbed):
    gh = EchoingGitHub()
    said: list[str] = []
    out = await flows.guard_pr(
        GitHubApp("1", KEY, transport=httpx.MockTransport(gh)),
        "o/r", 5, suite=SUITE, target=None, questions=["q"], progress=said.append,
    )  # fmt: skip
    assert TOKEN not in json.dumps(out, default=str)
    assert not any(TOKEN in s for s in said)
    assert not any(TOKEN in b for b in gh.bodies)  # nothing we sent to GitHub carries it


async def test_token_echoed_by_github_is_not_repeated_in_our_error(stubbed):
    """GitHubError messages become job errors and job events: if GitHub echoes the bearer
    token in an error body, the message we raise must not carry it."""
    gh = EchoingGitHub(fail_patch=True)
    with pytest.raises(GitHubError) as exc:
        await flows.guard_pr(
            GitHubApp("1", KEY, transport=httpx.MockTransport(gh)),
            "o/r", 5, suite=SUITE, target=None, questions=["q"],
        )  # fmt: skip
    assert TOKEN not in str(exc.value)
