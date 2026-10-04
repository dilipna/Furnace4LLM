"""Blob storage. Keys are always prefixed `org/<org_id>/project/<project_id>/...`
so tenant data is separable and deletable as a unit."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from furnace.settings import get_settings


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def get(self, key: str) -> bytes: ...
    def path(self, key: str) -> Path: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError(f"blob key escapes store: {key!r}")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def path(self, key: str) -> Path:
        return self._resolve(key)

    def delete_prefix(self, prefix: str) -> None:
        p = self._resolve(prefix)
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def get_blob_store() -> BlobStore:
    s = get_settings()
    if s.blob_backend == "local":
        return LocalBlobStore(s.blob_dir)
    raise NotImplementedError(f"blob backend {s.blob_backend!r} is not configured")


def tenant_prefix(org_id: object, project_id: object) -> str:
    return f"org/{org_id}/project/{project_id}"
