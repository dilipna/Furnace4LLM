"""Standard-library host for a researcher's model adapter (Furnace protocol furnace-chat-v1).

Runs inside the researcher's own pinned container image; it imports nothing from
Furnace. The adapter module supplies a factory returning an object with:

    load(weights_dir: str | None) -> None
    generate(messages: list[dict], max_tokens: int, temperature: float) -> tuple[str, str]
        returns (text, finish_reason) with finish_reason "stop" or "length"
    reset() -> None            # optional; called before every request

Requests are served one at a time. If FURNACE_API_KEY is set, completions require
"Authorization: Bearer <key>". Errors return a fixed category, never adapter text.
"""

from __future__ import annotations

import argparse
import hmac
import importlib
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MAX_BODY = 1 << 20


class Host:
    def __init__(self, adapter: Any, model_id: str, max_tokens: int, key: str | None):
        self.adapter, self.model_id, self.max_tokens, self.key = adapter, model_id, max_tokens, key
        self.state = "loading"
        self.lock = threading.Lock()
        self.counters = {"requests_total": 0, "errors_total": 0, "generation_seconds_total": 0.0}

    def load(self, weights: str | None) -> None:
        try:
            self.adapter.load(weights)
            self.state = "ready"
        except Exception:
            self.state = "failed"
            print("furnace-adapter: load failed", file=sys.stderr, flush=True)

    def complete(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        messages = body.get("messages")
        max_tokens = body.get("max_tokens", self.max_tokens)
        temperature = body.get("temperature", 0)
        if (
            body.get("model") != self.model_id
            or body.get("stream", False) is not False
            or not isinstance(messages, list)
            or not messages
            or not all(
                isinstance(m, dict) and isinstance(m.get("content"), str) and m.get("role")
                for m in messages
            )
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= self.max_tokens
            or not isinstance(temperature, int | float)
        ):
            return 400, {"error": {"type": "invalid_request"}}
        with self.lock:
            began = time.monotonic()
            self.counters["requests_total"] += 1
            try:
                if callable(getattr(self.adapter, "reset", None)):
                    self.adapter.reset()
                text, finish = self.adapter.generate(messages, max_tokens, float(temperature))
                if not isinstance(text, str) or finish not in {"stop", "length"}:
                    raise TypeError("adapter returned an invalid result")
            except Exception:
                self.counters["errors_total"] += 1
                print("furnace-adapter: generate failed", file=sys.stderr, flush=True)
                return 500, {"error": {"type": "adapter_error"}}
            finally:
                self.counters["generation_seconds_total"] += time.monotonic() - began
        return 200, {
            "id": "chatcmpl-" + uuid.uuid4().hex,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": finish,
                }
            ],
        }


def handler(host: Host) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "furnace-pyserve"

        def log_message(self, format: str, *args: Any) -> None:
            # Request lines only (method/path/status); bodies are never logged.
            print("furnace-adapter:", format % args, file=sys.stderr, flush=True)

        def send(self, status: int, value: Any, kind: str = "application/json") -> None:
            raw = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self) -> bool:
            if not host.key:
                return True
            supplied = self.headers.get("Authorization", "")
            return hmac.compare_digest(supplied.encode(), f"Bearer {host.key}".encode())

        def do_GET(self) -> None:
            if self.path == "/health":
                status = {"ready": 200, "loading": 503}.get(host.state, 500)
                self.send(status, {"status": "ok" if status == 200 else host.state})
            elif self.path == "/v1/models":
                self.send(200, {"object": "list", "data": [{"id": host.model_id}]})
            elif self.path == "/metrics":
                if not self.authorized():
                    return self.send(401, {"error": {"type": "unauthorized"}})
                lines = [f"furnace_adapter:{k} {v}" for k, v in host.counters.items()]
                self.send(200, ("\n".join(lines) + "\n").encode(), "text/plain")
            else:
                self.send(404, {"error": {"type": "not_found"}})

        def do_POST(self) -> None:
            # Read the bounded body before any reply: closing a socket with unread
            # request bytes makes some TCP stacks reset the connection, so the client
            # would see a reset instead of the 401/503 it should act on.
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                self.close_connection = True
                return self.send(
                    400 if length <= MAX_BODY else 413, {"error": {"type": "invalid_request"}}
                )
            raw = self.rfile.read(length)
            if self.path != "/v1/chat/completions":
                return self.send(404, {"error": {"type": "not_found"}})
            if not self.authorized():
                return self.send(401, {"error": {"type": "unauthorized"}})
            if host.state != "ready":
                return self.send(503, {"error": {"type": "not_ready"}})
            try:
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self.send(400, {"error": {"type": "invalid_request"}})
            self.send(*host.complete(body))

    return Handler


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="furnace-pyserve")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 -- internal container network
    parser.add_argument("--weights")
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args(argv)
    sys.path.insert(0, args.code)
    module_name, factory_name = args.adapter.split(":")
    adapter = getattr(importlib.import_module(module_name), factory_name)()
    host = Host(adapter, args.model_id, args.max_tokens, os.environ.get("FURNACE_API_KEY"))
    server = ThreadingHTTPServer((args.host, args.port), handler(host))
    threading.Thread(target=host.load, args=(args.weights,), daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
