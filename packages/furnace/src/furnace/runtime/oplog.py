"""Bounded, structured operations log for the local workspace.

One JSON object per line: time, project, event kind, request/launch identifiers,
durations, token counts and error categories. Prompts, outputs and secrets are not
accepted (rejected keys), so the log can be shared for support without redaction.
Files rotate by size and old entries are pruned by the project's retention setting.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

FORBIDDEN = {"input", "output", "prompt", "messages", "content", "api_key", "key", "token"}
ROTATE_BYTES = 1 << 20
KEEP_FILES = 5


class OperationsLog:
    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / "operations.jsonl"
        self._lock = threading.Lock()

    def append(self, project_id: str | None, kind: str, **fields: Any) -> None:
        bad = FORBIDDEN.intersection(fields)
        if bad:
            raise ValueError(f"operations log refuses content fields: {sorted(bad)}")
        entry = {"at": datetime.now(UTC).isoformat(), "project_id": project_id, "kind": kind}
        entry.update(fields)
        line = json.dumps(entry, sort_keys=True, default=str)
        if len(line) > 4096:
            line = json.dumps(
                {**{k: entry[k] for k in ("at", "project_id", "kind")}, "truncated": True}
            )
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size > ROTATE_BYTES:
                self._rotate()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def _rotate(self) -> None:
        for index in range(KEEP_FILES - 1, 0, -1):
            older = self.directory / f"operations.{index}.jsonl"
            newer = self.path if index == 1 else self.directory / f"operations.{index - 1}.jsonl"
            if newer.exists():
                newer.replace(older)

    def files(self) -> list[Path]:
        rotated = sorted(
            self.directory.glob("operations.*.jsonl"),
            key=lambda p: int(p.stem.split(".")[1]),
            reverse=True,
        )
        return [*rotated, self.path] if self.path.exists() else rotated

    def read(self, project_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        with self._lock:
            for path in self.files():
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if project_id is None or entry.get("project_id") == project_id:
                        entries.append(entry)
        return entries[-max(1, min(limit, 1000)) :]

    def prune(self, retention_days: dict[str | None, int], default_days: int = 7) -> int:
        """Drop entries older than each project's retention; returns how many were removed."""
        now = datetime.now(UTC)
        removed = 0
        with self._lock:
            for path in self.files():
                kept = []
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        entry = json.loads(line)
                        at = datetime.fromisoformat(entry["at"])
                    except (ValueError, KeyError, TypeError):
                        removed += 1
                        continue
                    days = retention_days.get(entry.get("project_id"), default_days)
                    if now - at <= timedelta(days=days):
                        kept.append(line)
                    else:
                        removed += 1
                path.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
        return removed
