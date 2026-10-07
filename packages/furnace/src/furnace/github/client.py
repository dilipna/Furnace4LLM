"""GitHub App integration: authentication, least-privilege tokens, webhooks,
draft pull requests through the Git Data API, and check runs.

Permissions the App requests: Metadata (read), Contents (read & write),
Pull requests (read & write), Checks (read & write). Every job mints its own
installation token scoped to one repository and only the permissions it needs:
scans get contents:read; pull-request creation (only after explicit, audited
write consent) gets contents:write + pull_requests:write; Guard gets checks:write.
Furnace never merges and never pushes to a default branch.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "furnace",
}

SCAN_PERMISSIONS = {"contents": "read", "metadata": "read"}
PR_PERMISSIONS = {"contents": "write", "pull_requests": "write", "metadata": "read"}
CHECKS_PERMISSIONS = {"checks": "write", "metadata": "read"}
# Guard reads both revisions of a pull request and reports a check run; nothing else.
GUARD_PERMISSIONS = {
    "contents": "read",
    "pull_requests": "read",
    "checks": "write",
    "metadata": "read",
}


class GitHubError(Exception):
    pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_jwt(app_id: str, private_key_pem: str, now: int | None = None) -> str:
    """RS256 JWT for authenticating as the GitHub App (valid 9 minutes, issued 60 s in the past)."""
    now = int(now if now is not None else time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {"iat": now - 60, "exp": now + 540, "iss": app_id}, separators=(",", ":")
        ).encode()
    )
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise GitHubError("GitHub App key must be an RSA private key")
    signature = key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64url(signature)}"


def verify_webhook(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Constant-time check of X-Hub-Signature-256."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@dataclass
class GitHubApp:
    app_id: str
    private_key_pem: str
    transport: httpx.AsyncBaseTransport | None = None

    async def app_info(self) -> dict[str, Any]:
        """The App itself and its installations: proves the id and key are right."""
        jwt = app_jwt(self.app_id, self.private_key_pem)
        async with httpx.AsyncClient(
            base_url=API,
            headers={**HEADERS, "Authorization": f"Bearer {jwt}"},
            transport=self.transport,
            timeout=20,
        ) as c:
            app = await c.get("/app")
            inst = await c.get("/app/installations")
        if app.status_code != 200:
            raise GitHubError(f"GET /app failed: {app.status_code} {app.text[:200]}")
        return {
            "slug": app.json().get("slug"),
            "name": app.json().get("name"),
            "permissions": app.json().get("permissions", {}),
            "events": app.json().get("events", []),
            "installations": [
                {"id": i["id"], "account": (i.get("account") or {}).get("login")}
                for i in (inst.json() if inst.status_code == 200 else [])
            ],
        }

    async def installation_for(self, full_name: str) -> int:
        """Installation id of this App on `owner/name` (404 -> the App is not installed there)."""
        jwt = app_jwt(self.app_id, self.private_key_pem)
        async with httpx.AsyncClient(
            base_url=API, headers=HEADERS, transport=self.transport, timeout=20
        ) as c:
            r = await c.get(
                f"/repos/{full_name}/installation", headers={"Authorization": f"Bearer {jwt}"}
            )
        if r.status_code == 404:
            raise GitHubError(f"the GitHub App is not installed on {full_name}")
        if r.status_code != 200:
            raise GitHubError(f"installation lookup failed: {r.status_code} {r.text[:200]}")
        return int(r.json()["id"])

    async def installation_token(
        self, installation_id: int, *, repository: str, permissions: dict[str, str]
    ) -> str:
        """Token limited to one repository (name, not owner/name) and the given permissions."""
        jwt = app_jwt(self.app_id, self.private_key_pem)
        async with httpx.AsyncClient(
            base_url=API, headers=HEADERS, transport=self.transport, timeout=20
        ) as c:
            r = await c.post(
                f"/app/installations/{installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {jwt}"},
                json={"repositories": [repository], "permissions": permissions},
            )
        if r.status_code != 201:
            raise GitHubError(f"installation token request failed: {r.status_code} {r.text[:200]}")
        return r.json()["token"]


@dataclass
class Repo:
    full_name: str  # owner/name
    token: str
    transport: httpx.AsyncBaseTransport | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=API,
            headers={**HEADERS, "Authorization": f"Bearer {self.token}"},
            transport=self.transport,
            timeout=30,
        )

    async def _req(self, c: httpx.AsyncClient, method: str, path: str, **kw: Any) -> dict[str, Any]:
        r = await c.request(method, f"/repos/{self.full_name}{path}", **kw)
        if r.status_code >= 400:
            raise GitHubError(f"{method} {path}: {r.status_code} {r.text[:300]}")
        return r.json() if r.content else {}

    async def pull(self, number: int) -> dict[str, Any]:
        """{number, title, base_ref, base_sha, head_ref, head_sha, head_repo} of a pull request."""
        async with self._client() as c:
            pr = await self._req(c, "GET", f"/pulls/{number}")
        return {
            "number": pr["number"],
            "title": pr["title"],
            "base_ref": pr["base"]["ref"],
            "base_sha": pr["base"]["sha"],
            "head_ref": pr["head"]["ref"],
            "head_sha": pr["head"]["sha"],
            "head_repo": (pr["head"].get("repo") or {}).get("full_name"),
        }

    async def default_branch(self) -> tuple[str, str]:
        """(default branch, its head commit sha)."""
        async with self._client() as c:
            repo = await self._req(c, "GET", "")
            branch = repo["default_branch"]
            ref = await self._req(c, "GET", f"/git/ref/heads/{branch}")
        return branch, ref["object"]["sha"]

    async def compare(self, base: str, head: str) -> dict[str, Any]:
        async with self._client() as c:
            return await self._req(c, "GET", f"/compare/{base}...{head}")

    async def open_draft_pr(
        self,
        *,
        base_branch: str,
        new_branch: str,
        files: dict[str, str],
        title: str,
        body: str,
        commit_message: str,
        base_sha: str | None = None,
    ) -> dict[str, Any]:
        """Create one commit with `files` on a new branch and open a DRAFT pull request.
        Atomic: the branch ref is created only after the commit exists."""
        if new_branch == base_branch or new_branch in ("main", "master"):
            raise GitHubError("refusing to write to a base/default branch")
        async with self._client() as c:
            if base_sha is None:
                ref = await self._req(c, "GET", f"/git/ref/heads/{base_branch}")
                base_sha = ref["object"]["sha"]
            base_commit = await self._req(c, "GET", f"/git/commits/{base_sha}")
            entries = []
            for path, content in sorted(files.items()):
                blob = await self._req(
                    c, "POST", "/git/blobs", json={"content": content, "encoding": "utf-8"}
                )
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
            tree = await self._req(
                c,
                "POST",
                "/git/trees",
                json={"base_tree": base_commit["tree"]["sha"], "tree": entries},
            )
            commit = await self._req(
                c,
                "POST",
                "/git/commits",
                json={"message": commit_message, "tree": tree["sha"], "parents": [base_sha]},
            )
            await self._req(
                c,
                "POST",
                "/git/refs",
                json={"ref": f"refs/heads/{new_branch}", "sha": commit["sha"]},
            )
            pr = await self._req(
                c,
                "POST",
                "/pulls",
                json={
                    "title": title,
                    "head": new_branch,
                    "base": base_branch,
                    "body": body,
                    "draft": True,
                },
            )
            return {
                "number": pr["number"],
                "url": pr["html_url"],
                "commit": commit["sha"],
                "branch": new_branch,
            }

    async def create_check(self, head_sha: str, name: str = "Furnace Guard") -> int:
        async with self._client() as c:
            r = await self._req(
                c,
                "POST",
                "/check-runs",
                json={"name": name, "head_sha": head_sha, "status": "in_progress"},
            )
            return int(r["id"])

    async def complete_check(
        self,
        check_id: int,
        *,
        conclusion: str,
        title: str,
        summary: str,
        text: str = "",
        annotations: list[dict[str, Any]] | None = None,
    ) -> None:
        if conclusion not in ("success", "neutral", "failure", "action_required"):
            raise GitHubError(f"invalid conclusion {conclusion}")
        output: dict[str, Any] = {"title": title, "summary": summary[:65000], "text": text[:65000]}
        if annotations:
            output["annotations"] = annotations[:50]
        async with self._client() as c:
            await self._req(
                c,
                "PATCH",
                f"/check-runs/{check_id}",
                json={"status": "completed", "conclusion": conclusion, "output": output},
            )
