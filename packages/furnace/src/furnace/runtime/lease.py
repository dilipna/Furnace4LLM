"""Process-lifetime workspace ownership; OS locks release after a crash."""

from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType
from typing import BinaryIO


class WorkspaceBusy(RuntimeError):
    pass


class WorkspaceLease:
    def __init__(self, workspace: Path):
        self.path = workspace / "studio.lock"
        self.file: BinaryIO | None = None

    def __enter__(self) -> WorkspaceLease:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise WorkspaceBusy(
                "This Studio workspace is already open. Close its application or choose another --workspace"
            ) from None
        self.file = stream
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.file is None:
            return
        try:
            self.file.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()
            self.file = None
