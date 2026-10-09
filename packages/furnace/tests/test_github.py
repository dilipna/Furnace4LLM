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
        "commit": "commit1",
        "branch": "furnace/forge-1",
    }
    seq = [(m, p.removeprefix(r)) for m, p, _, _ in rec.calls]
    assert seq == [
        ("GET", "/git/ref/heads/main"),
        ("GET", "/git/commits/base1"),
        ("POST", "/git/blobs"),
        ("POST", "/git/blobs"),
        ("POST", "/git/trees"),
        ("POST", "/git/commits"),
        ("POST", "/git/refs"),
        ("POST", "/pulls"),
    ]
    pr_body = rec.calls[-1][2]
    assert pr_body["draft"] is True and pr_body["base"] == "main"
    commit = next(b for m, p, b, _ in rec.calls if p.endswith("/git/commits") and m == "POST")
    assert commit["parents"] == ["base1"]


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


async def test_draft_pr_takes_next_free_branch_and_caps_the_body():
    r = "/repos/acme/app"
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else {}
        calls.append((req.method, req.url.path.removeprefix(r), body))
        p = req.url.path.removeprefix(r)
        if p == "/git/refs":
            if body["ref"] in ("refs/heads/furnace/forge-1", "refs/heads/furnace/forge-1-2"):
                return httpx.Response(422, json={"message": "Reference already exists"})
            return httpx.Response(201, json={})
        if p == "/pulls":
            return httpx.Response(201, json={"number": 9, "html_url": "u"})
        if p.startswith("/git/commits/"):
            return httpx.Response(200, json={"tree": {"sha": "t0"}})
        return httpx.Response(201, json={"sha": "s"})

    repo = Repo("acme/app", "t", transport=httpx.MockTransport(handler))
    out = await repo.open_draft_pr(
        base_branch="main", new_branch="furnace/forge-1", files={"a": "x"}, title="t",
        body="x" * 70_000, commit_message="m", base_sha="b",
    )  # fmt: skip
    assert out["branch"] == "furnace/forge-1-3"
    pr = calls[-1][2]
    assert pr["head"] == "furnace/forge-1-3" and len(pr["body"]) < 65_536
    assert pr["body"].endswith("65,536 characters)_")


async def test_draft_pr_other_ref_errors_still_raise():
    def handler(req: httpx.Request) -> httpx.Response:
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
