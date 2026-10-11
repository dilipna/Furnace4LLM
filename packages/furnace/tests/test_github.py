import base64
import json

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from furnace.github.client import (
    PR_PERMISSIONS,
    GitHubApp,
    GitHubError,
    Repo,
    app_jwt,
    verify_webhook,
)

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def test_app_jwt_is_valid_rs256():
    token = app_jwt("12345", PEM, now=1_000_000)
    h, p, s = token.split(".")
    assert json.loads(_b64d(h)) == {"alg": "RS256", "typ": "JWT"}
    assert json.loads(_b64d(p)) == {"iat": 999_940, "exp": 1_000_540, "iss": "12345"}
    KEY.public_key().verify(
        _b64d(s), f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256()
    )  # raises if invalid


@pytest.mark.adversarial
def test_webhook_signature():
    import hashlib
    import hmac

    body = b'{"action":"opened"}'
    good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_webhook("s3cret", body, good)
    assert not verify_webhook("s3cret", body + b" ", good)
    assert not verify_webhook("s3cret", body, None)
    assert not verify_webhook("other", body, good)


class Recorder:
    def __init__(self, responses):
        self.calls = []
        self.responses = responses

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append(
            (request.method, request.url.path, body, request.headers.get("authorization"))
        )
        for (method, prefix), (status, payload) in self.responses.items():
            if request.method == method and request.url.path.startswith(prefix):
                return httpx.Response(status, json=payload)
        return httpx.Response(404, json={"message": "unexpected"})


@pytest.mark.adversarial
async def test_installation_token_is_scoped_to_one_repo_and_permissions():
    rec = Recorder({("POST", "/app/installations/77/access_tokens"): (201, {"token": "ghs_x"})})
    app = GitHubApp("1", PEM, transport=httpx.MockTransport(rec))
    assert (
        await app.installation_token(77, repository="support-rag-py", permissions=PR_PERMISSIONS)
        == "ghs_x"
    )
    _, _, body, auth = rec.calls[0]
    assert body == {"repositories": ["support-rag-py"], "permissions": PR_PERMISSIONS}
    assert auth is not None and auth.startswith("Bearer ey")


async def test_open_draft_pr_uses_git_data_api_in_order():
    r = "/repos/acme/app"
    rec = Recorder(
        {
            ("GET", f"{r}/git/ref/heads/main"): (200, {"object": {"sha": "base1"}}),
            ("GET", f"{r}/git/commits/base1"): (200, {"tree": {"sha": "tree0"}}),
            ("POST", f"{r}/git/blobs"): (201, {"sha": "blob1"}),
            ("POST", f"{r}/git/trees"): (201, {"sha": "tree1"}),
            ("POST", f"{r}/git/commits"): (201, {"sha": "commit1"}),
            ("POST", f"{r}/git/refs"): (201, {"ref": "refs/heads/furnace/forge-1"}),
            ("POST", f"{r}/pulls"): (
                201,
                {"number": 5, "html_url": "https://github.com/acme/app/pull/5"},
            ),
        }
    )
    repo = Repo("acme/app", "ghs_x", transport=httpx.MockTransport(rec))
    out = await repo.open_draft_pr(
        base_branch="main",
        new_branch="furnace/forge-1",
        files={"a.py": "x", "b.py": "y"},
        title="t",
        body="b",
        commit_message="m",
    )
    assert out == {
        "number": 5,
        "url": "https://github.com/acme/app/pull/5",
        "state": "open",
        "commit": "commit1",
        "branch": "furnace/forge-1",
        "reused": False,
    }
    seq = [(m, p.removeprefix(r)) for m, p, _, _ in rec.calls]
    assert seq == [
        ("GET", "/git/ref/heads/main"),
        ("GET", "/git/commits/base1"),
        ("POST", "/git/blobs"),
        ("POST", "/git/blobs"),
        ("POST", "/git/trees"),
        ("GET", "/git/ref/heads/furnace/forge-1"),  # 404: the branch is free
        ("POST", "/git/commits"),
        ("POST", "/git/refs"),
        ("POST", "/pulls"),
    ]
    pr_body = rec.calls[-1][2]
    assert pr_body["draft"] is True and pr_body["base"] == "main"
    commit = next(b for m, p, b, _ in rec.calls if p.endswith("/git/commits") and m == "POST")
    assert commit["parents"] == ["base1"]


@pytest.mark.adversarial
async def test_never_writes_to_default_branch():
    repo = Repo("acme/app", "t", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(GitHubError, match="refusing"):
        await repo.open_draft_pr(
            base_branch="main", new_branch="main", files={}, title="", body="", commit_message=""
        )


async def test_check_run_lifecycle_and_conclusion_validation():
    r = "/repos/acme/app"
    rec = Recorder(
        {("POST", f"{r}/check-runs"): (201, {"id": 9}), ("PATCH", f"{r}/check-runs/9"): (200, {})}
    )
    repo = Repo("acme/app", "t", transport=httpx.MockTransport(rec))
    cid = await repo.create_check("sha1")
    await repo.complete_check(
        cid,
        conclusion="failure",
        title="p95 TTFT +154%",
        summary="blocked",
        annotations=[
            {
                "path": "app/prompts.py",
                "start_line": 62,
                "end_line": 66,
                "annotation_level": "failure",
                "message": "dynamic head",
            }
        ],
    )
    patch = rec.calls[-1][2]
    assert (
        patch["conclusion"] == "failure"
        and patch["output"]["annotations"][0]["path"] == "app/prompts.py"
    )
    with pytest.raises(GitHubError):
        await repo.complete_check(cid, conclusion="maybe", title="", summary="")


class FakeGitData:
    """A tiny in-memory GitHub for the Git Data + pulls endpoints open_draft_pr uses.
    Trees are content-addressed like Git's (same entries on the same base -> same sha)."""

    def __init__(self):
        self.refs: dict[str, str] = {}  # branch -> commit sha
        self.commits: dict[str, str] = {"base0": "tree-base"}  # commit -> tree
        self.pulls: list[dict] = []
        self.calls: list[tuple[str, str]] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        r = "/repos/acme/app"
        p = req.url.path.removeprefix(r)
        body = json.loads(req.content) if req.content else {}
        self.calls.append((req.method, p))
        if req.method == "POST" and p == "/git/blobs":
            return httpx.Response(201, json={"sha": "blob-" + body["content"]})
        if req.method == "POST" and p == "/git/trees":
            key = body["base_tree"] + "|" + ",".join(e["sha"] for e in body["tree"])
            return httpx.Response(201, json={"sha": "tree:" + key})
        if req.method == "POST" and p == "/git/commits":
            sha = f"c{len(self.commits)}"
            self.commits[sha] = body["tree"]
            return httpx.Response(201, json={"sha": sha})
        if req.method == "GET" and p.startswith("/git/commits/"):
            return httpx.Response(200, json={"tree": {"sha": self.commits[p.rsplit("/", 1)[1]]}})
        if req.method == "GET" and p.startswith("/git/ref/heads/"):
            branch = p.removeprefix("/git/ref/heads/")
            if branch not in self.refs:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(200, json={"object": {"sha": self.refs[branch]}})
        if req.method == "POST" and p == "/git/refs":
            branch = body["ref"].removeprefix("refs/heads/")
            if branch in self.refs:
                return httpx.Response(422, json={"message": "Reference already exists"})
            self.refs[branch] = body["sha"]
            return httpx.Response(201, json={})
        if req.method == "GET" and p == "/pulls":
            head = req.url.params["head"].split(":", 1)[1]
            return httpx.Response(200, json=[x for x in self.pulls if x["head"] == head])
        if req.method == "POST" and p == "/pulls":
            n = len(self.pulls) + 1
            self.pulls.append(
                {"number": n, "html_url": f"u/{n}", "head": body["head"], "state": "open",
                 "body": body["body"]}
            )  # fmt: skip
            return httpx.Response(201, json=self.pulls[-1])
        return httpx.Response(404, json={"message": f"unexpected {req.method} {p}"})


async def _open(gh, files=None, body="b"):
    repo = Repo("acme/app", "t", transport=httpx.MockTransport(gh))
    return await repo.open_draft_pr(
        base_branch="main", new_branch="furnace/forge-1", files=files or {"a.py": "x"},
        title="t", body=body, commit_message="m", base_sha="base0",
    )  # fmt: skip


async def test_retrying_the_same_change_never_opens_a_second_pull_request():
    gh = FakeGitData()
    first = await _open(gh)
    again = await _open(gh)
    assert first["reused"] is False and again["reused"] is True
    assert again["number"] == first["number"] and again["branch"] == "furnace/forge-1"
    assert len(gh.pulls) == 1 and list(gh.refs) == ["furnace/forge-1"]


async def test_a_pull_request_closed_by_a_human_is_not_reopened_or_duplicated():
    gh = FakeGitData()
    first = await _open(gh)
    gh.pulls[0]["state"] = "closed"
    again = await _open(gh)
    assert again["number"] == first["number"] and again["state"] == "closed"
    assert len(gh.pulls) == 1


async def test_crash_between_branch_and_pull_request_resumes_on_the_same_branch():
    gh = FakeGitData()
    await _open(gh)
    gh.pulls.clear()  # as if the process died after creating the ref
    out = await _open(gh)
    assert out["branch"] == "furnace/forge-1" and len(gh.pulls) == 1
    assert sum(1 for m, p in gh.calls if (m, p) == ("POST", "/git/refs")) == 1


@pytest.mark.adversarial
async def test_different_content_takes_the_next_branch_and_never_overwrites():
    gh = FakeGitData()
    first = await _open(gh, {"a.py": "x"})
    second = await _open(gh, {"a.py": "y"})
    assert second["branch"] == "furnace/forge-1-2" and second["number"] != first["number"]
    assert gh.refs["furnace/forge-1"] != gh.refs["furnace/forge-1-2"]
    assert not any(m in ("PATCH", "PUT", "DELETE") for m, _ in gh.calls)  # no ref rewrites


async def test_draft_pr_body_is_capped():
    gh = FakeGitData()
    await _open(gh, body="x" * 70_000)
    assert len(gh.pulls[0]["body"]) < 65_536
    assert gh.pulls[0]["body"].endswith("65,536 characters)_")


async def test_draft_pr_other_ref_errors_still_raise():
    def handler(req: httpx.Request) -> httpx.Response:
        if "/git/ref/heads/" in req.url.path:
            return httpx.Response(404, json={"message": "Not Found"})
        if req.url.path.endswith("/git/refs"):
            return httpx.Response(403, json={"message": "Resource not accessible by integration"})
        if "/git/commits/" in req.url.path:
            return httpx.Response(200, json={"tree": {"sha": "t0"}})
        return httpx.Response(201, json={"sha": "s"})

    repo = Repo("acme/app", "t", transport=httpx.MockTransport(handler))
    with pytest.raises(GitHubError, match="403"):
        await repo.open_draft_pr(
            base_branch="main", new_branch="furnace/x", files={"a": "x"}, title="t",
            body="b", commit_message="m", base_sha="b",
        )  # fmt: skip


@pytest.mark.adversarial
def test_github_errors_never_carry_credentials():
    from furnace.github.client import scrub

    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiIxMjMifQ.c2lnbmF0dXJlLXZhbHVlLWhlcmU"
    for secret in (
        "ghs_" + "a1B2c3D4e5" * 3,
        "ghp_" + "Z9y8X7w6V5" * 3,
        "github_pat_" + "11ABCDEFG0" * 3,
        jwt,
        "Bearer abcdefghijklmnopqrstuvwxyz012345",
    ):
        msg = str(GitHubError(f"401 bad credentials for {secret} in request"))
        assert secret not in msg and "[redacted]" in msg
    assert (
        scrub("PATCH /check-runs/1: 422 Unprocessable") == "PATCH /check-runs/1: 422 Unprocessable"
    )
