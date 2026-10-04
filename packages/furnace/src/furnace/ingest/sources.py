"""Materialize an evidence source into a local, safely extracted directory.

GitHub repositories are fetched as tarballs through the REST API (no `git
clone`: no hooks, submodules or LFS), then pass through the same safe
extractor as uploaded ZIPs.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from furnace.security.safe_extract import (
    ExtractLimits,
    ExtractStats,
    safe_extract_tar,
    safe_extract_zip,
)
from furnace.settings import get_settings

GITHUB_API = "https://api.github.com"
MAX_DOWNLOAD_BYTES = 100 * 2**20
_REPO_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9-]{1,39})/(?P<repo>[A-Za-z0-9._-]{1,100}?)(?:\.git)?(?:/tree/(?P<ref>[^?#]+))?/?$"
    r"|^(?P<owner2>[A-Za-z0-9-]{1,39})/(?P<repo2>[A-Za-z0-9._-]{1,100})$"
)


class SourceError(Exception):
    """User-facing error: bad input or an unavailable source."""


@dataclass(frozen=True)
class GitHubRef:
    owner: str
    repo: str
    ref: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_github(value: str) -> GitHubRef:
    m = _REPO_RE.match(value.strip())
    if not m:
        raise SourceError("expected a GitHub repository such as github.com/owner/repo")
    owner = m.group("owner") or m.group("owner2")
    repo = m.group("repo") or m.group("repo2")
    if repo in (".", ".."):
        raise SourceError("invalid repository name")
    return GitHubRef(owner, repo, m.group("ref"))


def _gh_headers(token: str | None) -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "furnace-scan",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def resolve_commit(ref: GitHubRef, token: str | None = None) -> tuple[str, str]:
    """Return (default_or_requested_branch, commit_sha)."""
    async with httpx.AsyncClient(base_url=GITHUB_API, headers=_gh_headers(token), timeout=20) as gh:
        r = await gh.get(f"/repos/{ref.full_name}")
        if r.status_code == 404:
            raise SourceError(f"repository {ref.full_name} not found or not public")
        if r.status_code == 403:
            raise SourceError("GitHub API rate limit reached; try again later or connect GitHub")
        r.raise_for_status()
        branch = ref.ref or r.json()["default_branch"]
        c = await gh.get(f"/repos/{ref.full_name}/commits/{branch}")
        if c.status_code in (404, 422):
            raise SourceError(f"ref {branch!r} not found in {ref.full_name}")
        c.raise_for_status()
        return branch, c.json()["sha"]


async def download_github_tarball(
    ref: GitHubRef, sha: str, dest: Path, token: str | None = None
) -> Path:
    """Stream the tarball for a commit to `dest`, enforcing a byte cap."""
    url = f"{GITHUB_API}/repos/{ref.full_name}/tarball/{sha}"
    async with (
        httpx.AsyncClient(headers=_gh_headers(token), timeout=60, follow_redirects=True) as client,
        client.stream("GET", url) as resp,
    ):
        if resp.status_code != 200:
            raise SourceError(
                f"could not download {ref.full_name}@{sha[:7]} (HTTP {resp.status_code})"
            )
        host = resp.url.host
        if host not in ("api.github.com", "codeload.github.com"):
            raise SourceError(f"unexpected redirect host {host}")
        size = 0
        with dest.open("wb") as f:
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise SourceError(
                        f"repository archive larger than {MAX_DOWNLOAD_BYTES // 2**20} MB"
                    )
                f.write(chunk)
    return dest


async def materialize_github(
    ref: GitHubRef, workdir: Path, token: str | None = None
) -> tuple[Path, str, str, ExtractStats]:
    branch, sha = await resolve_commit(ref, token)
    tarball = workdir / "repo.tar.gz"
    await download_github_tarball(ref, sha, tarball, token)
    root = workdir / "src"
    stats = safe_extract_tar(tarball, root, ExtractLimits(), strip_components=1)
    tarball.unlink(missing_ok=True)
    return root, branch, sha, stats


def materialize_zip(zip_path: Path, workdir: Path) -> tuple[Path, ExtractStats]:
    root = workdir / "src"
    stats = safe_extract_zip(zip_path, root, ExtractLimits())
    # Uploads often wrap everything in one top-level folder; scan from inside it.
    entries = [p for p in root.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0], stats
    return root, stats


def dev_fixture_root(name: str) -> Path:
    """Dev-only: scan a fixture from this repository without network access."""
    if get_settings().env != "dev":
        raise SourceError("local fixtures can only be scanned in development")
    base = Path(__file__).resolve().parents[5] / "fixtures" / "apps"
    target = (base / name).resolve()
    if not target.is_relative_to(base) or not target.is_dir():
        raise SourceError(f"unknown fixture {name!r}")
    return target


def new_workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="furnace-scan-"))
