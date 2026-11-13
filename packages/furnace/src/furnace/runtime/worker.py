"""Standalone isolated worker protocol. The only registered adapter is NOT a model."""

from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Protocol

LIMIT = 32768
SOCKET = "/tmp/furnace-worker.sock"  # noqa: S108 -- private container tmpfs, not a host temp file


class Adapter(Protocol):
    """A reviewed adapter owns loading, prediction, state reset and cleanup."""

    def predict(self, value: str) -> str: ...
    def reset(self) -> None: ...
    def close(self) -> None: ...


class FrameworkFixture:
    """Deterministic infrastructure fixture; no learned parameters or model weights."""

    def predict(self, value: str) -> str:
        return "framework:" + value.upper()

    def reset(self) -> None:
        pass

    def close(self) -> None:
        pass


def serve() -> None:
    adapter: Adapter = FrameworkFixture()
    # This worker runs only inside Linux; Windows type stubs omit AF_UNIX.
    family = getattr(socket, "AF_UNIX")  # noqa: B009 -- preserve cross-platform type checking
    server = socket.socket(family, socket.SOCK_STREAM)
    server.bind(SOCKET)
    server.listen(2)
    try:
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(2)
                raw = bytearray()
                while not raw.endswith(b"\n"):
                    chunk = connection.recv(4096)
                    if not chunk or len(raw) + len(chunk) > LIMIT:
                        raise ValueError("invalid worker request")
                    raw.extend(chunk)
                response: dict[str, Any]
                try:
                    request = json.loads(raw)
                    operation = request.get("operation")
                    if operation == "health":
                        response = {
                            "ready": True,
                            "adapter": "framework_fixture",
                            "model_execution": False,
                        }
                    elif operation == "crash":
                        os._exit(70)
                    elif operation == "timeout":
                        time.sleep(60)
                        response = {"error": "fixture timeout completed"}
                    elif operation == "error":
                        response = {"error": "injected framework error"}
                    elif operation == "predict":
                        value = request.get("input")
                        if not isinstance(value, str) or not 1 <= len(value) <= 4000:
                            raise ValueError("invalid fixture input")
                        adapter.reset()  # independent requests cannot share adapter state
                        response = {
                            "output": adapter.predict(value),
                            "adapter": "framework_fixture",
                            "model_execution": False,
                        }
                    else:
                        raise ValueError("unknown worker operation")
                except (ValueError, TypeError):
                    response = {"error": "invalid worker request"}
                connection.sendall(json.dumps(response).encode() + b"\n")
    finally:
        adapter.close()
        server.close()


if __name__ == "__main__":
    serve()
