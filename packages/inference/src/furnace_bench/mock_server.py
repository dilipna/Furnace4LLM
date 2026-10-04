"""Deterministic OpenAI-compatible SSE server for validating the benchmark client.

Behaviour per request (mirrors vLLM's stream shape):
  1. role-only chunk immediately (content ""), which must NOT count as TTFT
  2. after `ttft_ms`: first content token
  3. every `tpot_ms`: next token, until max_tokens tokens are sent
  4. finish chunk, usage chunk (if stream_options.include_usage), [DONE]

`max_concurrency` optionally limits concurrently *generating* requests to emulate
server-side queueing (queued time is part of TTFT, as on a real server).

The server records, per request, its own perf_counter timestamps of receipt and
of each token write, served at GET /_records. perf_counter is a system-wide
monotonic clock (QueryPerformanceCounter on Windows, CLOCK_MONOTONIC on Linux),
so a client in another process can compare its timestamps with the server's:
client TTFT minus server TTFT is the client's measurement overhead. Run it as a
separate process for timing work; sharing a process means sharing the GIL.

Implemented on raw asyncio streams (HTTP/1.1, chunked transfer, keep-alive) to
keep furnace-bench free of web-framework dependencies.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockConfig:
    ttft_ms: float = 50.0
    tpot_ms: float = 10.0
    max_concurrency: int | None = None
    model: str = "mock"


@dataclass
class ServerRecord:
    key: str
    recv: float
    first_token: float | None = None
    end: float | None = None
    n_tokens: int = 0
    token_writes: list[float] = field(default_factory=list)


class MockServer:
    def __init__(
        self, config: MockConfig | None = None, host: str = "127.0.0.1", port: int = 0
    ) -> None:
        self.config = config or MockConfig()
        self.host, self.port = host, port
        self.records: list[ServerRecord] = []
        self.requests_total = 0
        self._server: asyncio.base_events.Server | None = None
        self._sem: asyncio.Semaphore | None = None

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self.config.max_concurrency:
            self._sem = asyncio.Semaphore(self.config.max_concurrency)
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    # ---------------------------------------------------------------- http
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                request_line = await reader.readline()
                if not request_line:
                    break
                method, path, _ = request_line.decode().split(" ", 2)
                headers: dict[str, str] = {}
                while True:
                    line = await reader.readline()
                    if line in (b"\r\n", b"\n", b""):
                        break
                    k, _, v = line.decode().partition(":")
                    headers[k.strip().lower()] = v.strip()
                body = b""
                if "content-length" in headers:
                    body = await reader.readexactly(int(headers["content-length"]))
                keep = await self._route(method, path, body, writer)
                if not keep or headers.get("connection", "").lower() == "close":
                    break
        except (ConnectionResetError, asyncio.IncompleteReadError, BrokenPipeError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    async def _send_simple(
        self, writer: asyncio.StreamWriter, status: str, body: bytes, ctype: str
    ) -> None:
        head = f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n\r\n"
        writer.write(head.encode() + body)
        await writer.drain()

    async def _chunk(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        writer.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        await writer.drain()

    async def _route(
        self, method: str, path: str, body: bytes, writer: asyncio.StreamWriter
    ) -> bool:
        if method == "GET" and path.endswith("/v1/models"):
            payload = {"object": "list", "data": [{"id": self.config.model, "object": "model"}]}
            await self._send_simple(
                writer, "200 OK", json.dumps(payload).encode(), "application/json"
            )
            return True
        if method == "GET" and path == "/_records":
            rows = [
                {
                    "key": r.key,
                    "recv": r.recv,
                    "first_token": r.first_token,
                    "end": r.end,
                    "n_tokens": r.n_tokens,
                    "last_token": r.token_writes[-1] if r.token_writes else None,
                }
                for r in self.records
            ]
            await self._send_simple(writer, "200 OK", json.dumps(rows).encode(), "application/json")
            return True
        if method == "GET" and path == "/metrics":
            text = f"mock:requests_total {self.requests_total}\n".encode()
            await self._send_simple(writer, "200 OK", text, "text/plain")
            return True
        if method == "POST" and path.endswith("/chat/completions"):
            await self._chat(json.loads(body or b"{}"), writer)
            return True
        await self._send_simple(writer, "404 Not Found", b"{}", "application/json")
        return True

    # ---------------------------------------------------------------- generation
    async def _chat(self, req: dict[str, Any], writer: asyncio.StreamWriter) -> None:
        recv = time.perf_counter()
        self.requests_total += 1
        messages = req.get("messages") or []
        user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
        )
        key = user.split(" ", 1)[0] if user else ""
        prompt_tokens = sum(len(str(m.get("content", "")).split()) for m in messages)
        n = int(req.get("max_tokens") or 16)
        rec = ServerRecord(key=key, recv=recv)
        self.records.append(rec)
        cid = f"chatcmpl-mock{self.requests_total}"

        def chunk(delta: dict[str, Any], finish: str | None = None) -> bytes:
            obj = {
                "id": cid,
                "object": "chat.completion.chunk",
                "model": self.config.model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return b"data: " + json.dumps(obj).encode() + b"\n\n"

        if not req.get("stream"):
            await self._generate_timing(rec, n, None)
            body = {
                "id": cid,
                "object": "chat.completion",
                "model": self.config.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": " tok" * n},
                        "finish_reason": "length",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": n,
                    "total_tokens": prompt_tokens + n,
                },
            }
            await self._send_simple(writer, "200 OK", json.dumps(body).encode(), "application/json")
            return

        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            b"Cache-Control: no-cache\r\nTransfer-Encoding: chunked\r\n\r\n"
        )
        await self._chunk(writer, chunk({"role": "assistant", "content": ""}))

        async def emit(i: int) -> None:
            await self._chunk(writer, chunk({"content": " tok"}))

        await self._generate_timing(rec, n, emit)
        await self._chunk(writer, chunk({}, finish="length"))
        if (req.get("stream_options") or {}).get("include_usage"):
            usage = {
                "id": cid,
                "object": "chat.completion.chunk",
                "model": self.config.model,
                "choices": [],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": n,
                    "total_tokens": prompt_tokens + n,
                },
            }
            await self._chunk(writer, b"data: " + json.dumps(usage).encode() + b"\n\n")
        await self._chunk(writer, b"data: [DONE]\n\n")
        await self._chunk(writer, b"")  # zero-length chunk terminates the body
        rec.end = time.perf_counter()

    async def _generate_timing(self, rec: ServerRecord, n: int, emit: Any) -> None:
        """Emit n tokens on an absolute schedule (no cumulative drift)."""
        cm = self._sem if self._sem is not None else contextlib.nullcontext()
        async with cm:  # type: ignore[attr-defined]
            loop = asyncio.get_running_loop()
            start = loop.time()
            for i in range(n):
                due = start + (self.config.ttft_ms + i * self.config.tpot_ms) / 1000.0
                delay = due - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                if emit is not None:
                    await emit(i)
                now = time.perf_counter()
                if rec.first_token is None:
                    rec.first_token = now
                rec.token_writes.append(now)
                rec.n_tokens += 1
