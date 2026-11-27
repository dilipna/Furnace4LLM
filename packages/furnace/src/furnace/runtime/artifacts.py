"""Content-addressed artifact store with resumable, verified downloads.

A file becomes usable only after its full SHA-256 and size match the pinned recipe;
it is then published with an atomic rename. An interrupted download leaves only a
private partial file, resumed with an HTTP range on the next attempt and discarded
if it can never match. Weights are data handed to an isolated server, never imported.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from furnace.runtime.catalog import Artifact

CHUNK = 1 << 20
Progress = Callable[[int, int], None]


class ArtifactError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _https_only(request: httpx.Request) -> None:
    # Every hop, including redirects to a CDN, must stay on HTTPS.
    if request.url.scheme != "https":
        raise ArtifactError("download_redirect_not_https")


def file_sha256(path: Path, cancel: threading.Event | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            if cancel is not None and cancel.is_set():
                raise ArtifactError("verification_cancelled")
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactStore:
    def __init__(self, root: Path, client: httpx.Client | None = None):
        # Docker bind mounts require absolute sources. Resolve once so a relative
        # cache also keeps its identity if the caller's working directory changes.
        self.root = root.resolve()
        self.blobs = self.root / "blobs" / "sha256"
        self.partial = self.root / "partial"
        self._client = client
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def path(self, artifact: Artifact) -> Path:
        return self.blobs / artifact.sha256

    def _lock(self, sha: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(sha, threading.Lock())

    def present(self, artifact: Artifact) -> bool:
        """Cheap check used for status; full verification happens on prepare and launch."""
        final = self.path(artifact)
        return final.is_file() and final.stat().st_size == artifact.size

    def verify(self, artifact: Artifact, cancel: threading.Event | None = None) -> Path:
        final = self.path(artifact)
        if not final.is_file() or final.is_symlink() or final.stat().st_size != artifact.size:
            raise ArtifactError("artifact_missing")
        if file_sha256(final, cancel) != artifact.sha256:
            # Never serve altered weights; quarantine for owner inspection instead of deleting.
            quarantine = self.root / "quarantine"
            quarantine.mkdir(parents=True, exist_ok=True)
            final.chmod(stat.S_IREAD | stat.S_IWRITE)
            os.replace(final, quarantine / f"{artifact.sha256}-{int(time.time())}")
            raise ArtifactError("artifact_digest_mismatch")
        return final

    def status(self, artifact: Artifact) -> dict[str, int | str]:
        if self.present(artifact):
            return {"state": "present", "bytes": artifact.size, "size": artifact.size}
        part = self.partial / f"{artifact.sha256}.part"
        done = part.stat().st_size if part.is_file() else 0
        return {"state": "partial" if done else "absent", "bytes": done, "size": artifact.size}

    def fetch(
        self,
        artifact: Artifact,
        progress: Progress | None = None,
        cancel: threading.Event | None = None,
        attempts: int = 4,
    ) -> Path:
        with self._lock(artifact.sha256):
            if self.present(artifact):
                return self.verify(artifact, cancel)
            self.blobs.mkdir(parents=True, exist_ok=True)
            self.partial.mkdir(parents=True, exist_ok=True)
            part = self.partial / f"{artifact.sha256}.part"
            needed = artifact.size - (part.stat().st_size if part.is_file() else 0)
            if shutil.disk_usage(self.root).free < needed + 64 * CHUNK:
                raise ArtifactError("insufficient_disk_space")
            failure = "download_failed"
            for attempt in range(attempts):
                try:
                    self._download(artifact, part, progress, cancel)
                    break
                except httpx.TransportError:
                    failure = "download_network_error"
                    if cancel is not None and cancel.wait(min(2**attempt, 8)):
                        raise ArtifactError("download_cancelled") from None
            else:
                raise ArtifactError(failure)
            if file_sha256(part, cancel) != artifact.sha256:
                part.unlink(missing_ok=True)
                raise ArtifactError("download_digest_mismatch")
            final = self.path(artifact)
            os.replace(part, final)
            # Read-only for everyone: the server runs as an unprivileged container user.
            final.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            (self.blobs / f"{artifact.sha256}.json").write_text(
                json.dumps({"url": artifact.url, "size": artifact.size, "name": artifact.filename}),
                encoding="utf-8",
            )
            return final

    def _download(
        self,
        artifact: Artifact,
        part: Path,
        progress: Progress | None,
        cancel: threading.Event | None,
    ) -> None:
        offset = part.stat().st_size if part.is_file() else 0
        if offset > artifact.size:
            part.unlink()
            offset = 0
        if offset == artifact.size:
            return
        client = self._client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=60.0),
            event_hooks={"request": [_https_only]},
            headers={"User-Agent": "furnace-studio"},
        )
        try:
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            with client.stream("GET", artifact.url, headers=headers) as response:
                if offset and response.status_code == 200:
                    offset = 0  # server ignored the range: start over
                elif offset and response.status_code == 206:
                    start = response.headers.get("content-range", "").split(" ")[-1].split("-")[0]
                    if start != str(offset):
                        raise ArtifactError("download_range_mismatch")
                elif response.status_code != 200:
                    raise ArtifactError(f"download_http_{response.status_code}")
                with part.open("ab" if offset else "wb") as handle:
                    # Write as bytes arrive so a reset keeps its progress for a resume.
                    for chunk in response.iter_bytes():
                        if cancel is not None and cancel.is_set():
                            raise ArtifactError("download_cancelled")
                        offset += len(chunk)
                        if offset > artifact.size:
                            handle.close()
                            part.unlink(missing_ok=True)
                            raise ArtifactError("download_larger_than_pinned_size")
                        handle.write(chunk)
                        if progress is not None:
                            progress(offset, artifact.size)
            if offset != artifact.size:
                raise httpx.ReadError("download ended before the pinned size")
        finally:
            if self._client is None:
                with contextlib.suppress(Exception):
                    client.close()
