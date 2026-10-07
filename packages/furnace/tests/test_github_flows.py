"""GitHub flows against a mock GitHub: call sequence, token scopes, fork refusal, and that a
crash still completes the check run (never left spinning). Sandbox work is stubbed."""

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from furnace.github import flows
from furnace.github.client import GUARD_PERMISSIONS, GitHubApp, GitHubError
from furnace.guardian.execute import ItemResult
from furnace.guardian.impact import SuiteItem

KEY = (
    rsa.generate_private_key(public_exponent=65537, key_size=2048)
    .private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    .decode()
)


class FakeGitHub:
    def __init__(self, head_repo="o/r"):
        self.calls: list[tuple[str, str, dict]] = []
        self.head_repo = head_repo

    def __call__(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else {}
        self.calls.append((req.method, req.url.path, body))
        p = req.url.path
        if p == "/repos/o/r/installation":
            return httpx.Response(200, json={"id": 77})
        if p == "/app/installations/77/access_tokens":
            return httpx.Response(201, json={"token": "t-scoped"})
        if p == "/repos/o/r/pulls/5":
            return httpx.Response(
                200,
                json={
                    "number": 5,
                    "title": "add request id",
                    "base": {"ref": "main", "sha": "b" * 40},
                    "head": {"ref": "feat", "sha": "h" * 40, "repo": {"full_name": self.head_repo}},
                },
            )
        if p == "/repos/o/r/check-runs" and req.method == "POST":
            return httpx.Response(201, json={"id": 991})
        if p == "/repos/o/r/check-runs/991" and req.method == "PATCH":
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"message": f"unexpected {req.method} {p}"})


def _app(fake):
    return GitHubApp(app_id="123", private_key_pem=KEY, transport=httpx.MockTransport(fake))


@pytest.fixture
def stub_work(monkeypatch, tmp_path):
    async def fetch(full_name, sha, token, dest):
        assert token == "t-scoped"
        dest.mkdir(parents=True)
        (dest / "app.py").write_text("x = 1\n" if sha.startswith("b") else "x = 2\n")
        return dest

    monkeypatch.setattr(flows, "fetch_revision", fetch)
    monkeypatch.setattr(flows, "prepare", lambda b, h: (tmp_path / "work", b, h))
    return monkeypatch


SUITE = [SuiteItem("unit:tests/test_x.py", "unit", ["component:*"], {"code"}, always=True)]


async def test_guard_pr_reports_a_check_run(stub_work):
    stub_work.setattr(
        flows,
        "run_items",
        lambda items, ctx, progress: [ItemResult("unit:tests/test_x.py", "fail", "1 failed")],
    )
    fake = FakeGitHub()
    out = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert out["conclusion"] == "failure" and out["check_id"] == 991
    token_req = next(b for m, p, b in fake.calls if p.endswith("/access_tokens"))
    assert token_req == {"repositories": ["r"], "permissions": GUARD_PERMISSIONS}
    create = next(b for m, p, b in fake.calls if p == "/repos/o/r/check-runs")
    assert create["head_sha"] == "h" * 40 and create["status"] == "in_progress"
    done = next(b for m, p, b in fake.calls if m == "PATCH")
    assert done["conclusion"] == "failure" and "regression" in done["output"]["title"]
    # read-only flow: nothing but the check run is written
    writes = [(m, p) for m, p, _ in fake.calls if m in ("POST", "PATCH", "PUT", "DELETE")]
    assert {p for _, p in writes} <= {
        "/app/installations/77/access_tokens",
        "/repos/o/r/check-runs",
        "/repos/o/r/check-runs/991",
    }


async def test_guard_pr_crash_still_completes_the_check(stub_work):
    def boom(items, ctx, progress):
        raise RuntimeError("sandbox unavailable")

    stub_work.setattr(flows, "run_items", boom)
    fake = FakeGitHub()
    with pytest.raises(RuntimeError):
        await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    done = next(b for m, p, b in fake.calls if m == "PATCH")
    assert done["conclusion"] == "neutral" and "sandbox unavailable" in done["output"]["summary"]


async def test_fork_pull_requests_are_refused(stub_work):
    fake = FakeGitHub(head_repo="stranger/r")
    with pytest.raises(GitHubError, match="fork"):
        await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert not any(p.endswith("/check-runs") for _, p, _ in fake.calls)


async def test_app_not_installed_is_a_clear_error():
    def nothing(req):
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(GitHubError, match="not installed on o/r"):
        await GitHubApp(
            app_id="1", private_key_pem=KEY, transport=httpx.MockTransport(nothing)
        ).installation_for("o/r")


def test_cli_loads_suite_and_questions(tmp_path):
    from furnace import cli

    suite_file = tmp_path / "s.py"
    suite_file.write_text(
        "from furnace.guardian.impact import SuiteItem\nF1_SUITE = [SuiteItem('a', 'unit', [], set())]\n"
    )
    assert [i.key for i in cli._suite(str(suite_file))] == ["a"]
    qf = tmp_path / "q.json"
    qf.write_text(json.dumps([{"question": "one?"}, "two?"]))
    assert cli._questions(str(qf)) == ["one?", "two?"]
    assert cli._questions(None) == cli.DEFAULT_QUESTIONS
