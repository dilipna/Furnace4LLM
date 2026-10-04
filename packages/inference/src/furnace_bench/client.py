"""One streamed request, timed.

The timed path uses aiohttp. We measured httpx adding 3 ms (c=1) to 64 ms (c=16)
between our send timestamp and the server receiving the request on a busy event
loop, versus <1 ms for aiohttp at the same concurrency (see
tests/test_mock_accuracy.py, which enforces the bound against a mock server).

Timestamps use ``time.perf_counter()``: immediately before the request is handed
to aiohttp, and as each line arrives. TTFT is measured to the first chunk that
carries generated output; role-only first chunks (vLLM sends
``delta: {role: assistant, content: ""}``) do not count.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

import aiohttp

from furnace_bench.sse import DONE, SSEDecoder, inspect_chunk


@dataclass
class RequestTiming:
    ok: bool = False
    error: str | None = None  # ErrorClass value
    error_detail: str | None = None
    send: float = 0.0  # perf_counter at send
    headers: float | None = None
    first_byte: float | None = None
    first_token: float | None = None
    end: float | None = None
    chunk_times: list[float] = field(default_factory=list)  # perf_counter of output chunks
    usage: dict[str, Any] | None = None
    output_chars: int = 0

    def _ms(self, t: float | None) -> float | None:
        return None if t is None else (t - self.send) * 1000.0

    @property
    def ttft_ms(self) -> float | None:
        return self._ms(self.first_token)

    @property
    def e2e_ms(self) -> float | None:
        return self._ms(self.end)

    @property
    def headers_ms(self) -> float | None:
        return self._ms(self.headers)

    @property
    def first_byte_ms(self) -> float | None:
        return self._ms(self.first_byte)

    @property
    def chunk_gaps_ms(self) -> list[float]:
        return [(b - a) * 1000.0 for a, b in pairwise(self.chunk_times)]


class _TTFTTimeout(Exception):
    pass


def make_session(max_connections: int, read_timeout_s: float) -> aiohttp.ClientSession:
    connector = aiohttp.TCPConnector(
        limit=max_connections, limit_per_host=max_connections, ttl_dns_cache=300
    )
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=read_timeout_s)
    return aiohttp.ClientSession(connector=connector, timeout=timeout, auto_decompress=False)


def _classify_http(status: int) -> str:
    return "http_5xx" if status >= 500 else "http_4xx"


async def stream_chat(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    ttft_timeout_s: float = 60.0,
    total_timeout_s: float = 300.0,
) -> RequestTiming:
    """POST a streaming chat completion and time it. Never raises for request errors."""
    t = RequestTiming()

    async def _run() -> None:
        decoder = SSEDecoder()
        t.send = time.perf_counter()
        async with session.post(url, json=payload, headers=headers) as resp:
            t.headers = time.perf_counter()
            if resp.status >= 400:
                body = (await resp.read())[:300].decode(errors="replace")
                t.error, t.error_detail = _classify_http(resp.status), f"{resp.status}: {body}"
                t.end = time.perf_counter()
                return
            content = resp.content
            while True:
                if t.first_token is None:
                    remaining = ttft_timeout_s - (time.perf_counter() - t.send)
                    if remaining <= 0:
                        raise _TTFTTimeout
                    try:
                        raw = await asyncio.wait_for(content.readline(), remaining)
                    except asyncio.TimeoutError as exc:
                        raise _TTFTTimeout from exc
                else:
                    raw = await content.readline()
                if not raw:  # EOF
                    break
                now = time.perf_counter()
                if t.first_byte is None:
                    t.first_byte = now
                item = decoder.feed(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
                if item is None:
                    continue
                if item is DONE:
                    break
                info = inspect_chunk(item)  # type: ignore[arg-type]
                if info.error:
                    t.error, t.error_detail, t.end = "http_5xx", info.error, now
                    return
                if info.usage:
                    t.usage = info.usage
                if info.has_output:
                    if t.first_token is None:
                        t.first_token = now
                    t.chunk_times.append(now)
                    t.output_chars += info.n_choices_text_chars
            tail = decoder.flush()
            if isinstance(tail, str):
                info = inspect_chunk(tail)
                if info.usage:
                    t.usage = info.usage
        t.end = time.perf_counter()
        if t.first_token is None:
            t.error = "empty_output"
        else:
            t.ok = True

    try:
        await asyncio.wait_for(_run(), total_timeout_s)
    except _TTFTTimeout:
        t.error = "ttft_timeout"
    except asyncio.TimeoutError:
        # Overall budget or socket read timeout (aiohttp.ServerTimeoutError is a TimeoutError).
        t.error = "ttft_timeout" if t.first_token is None and t.headers is None else "total_timeout"
    except aiohttp.ClientConnectorError as exc:
        t.error, t.error_detail = "connect", str(exc)[:300]
    except (ValueError, KeyError) as exc:  # malformed JSON / unexpected shape
        t.error, t.error_detail = "stream_parse", str(exc)[:300]
    except aiohttp.ClientError as exc:
        t.error, t.error_detail = "other", f"{type(exc).__name__}: {exc}"[:300]
    if t.end is None:
        t.end = time.perf_counter()
    if t.send == 0.0:  # failed before the send timestamp was taken
        t.send = t.end
    if not t.ok and t.error is None:
        t.error = "other"
    return t


async def complete_chat(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    total_timeout_s: float = 300.0,
) -> RequestTiming:
    """Non-streaming request: only E2E is measurable."""
    t = RequestTiming()

    async def _run() -> None:
        t.send = time.perf_counter()
        async with session.post(url, json=payload, headers=headers) as resp:
            t.headers = time.perf_counter()
            raw = await resp.read()
            t.end = time.perf_counter()
            if resp.status >= 400:
                t.error = _classify_http(resp.status)
                t.error_detail = f"{resp.status}: {raw[:300].decode(errors='replace')}"
                return
        body = json.loads(raw)
        t.usage = body.get("usage")
        text = "".join(
            ((c.get("message") or {}).get("content") or c.get("text") or "")
            for c in body.get("choices") or []
        )
        t.output_chars = len(text)
        t.ok = bool(text) or bool(t.usage and t.usage.get("completion_tokens"))
        if not t.ok:
            t.error = "empty_output"

    try:
        await asyncio.wait_for(_run(), total_timeout_s)
    except asyncio.TimeoutError:
        t.error = "total_timeout"
    except aiohttp.ClientConnectorError as exc:
        t.error, t.error_detail = "connect", str(exc)[:300]
    except (ValueError, KeyError) as exc:
        t.error, t.error_detail = "stream_parse", str(exc)[:300]
    except aiohttp.ClientError as exc:
        t.error, t.error_detail = "other", f"{type(exc).__name__}: {exc}"[:300]
    if t.end is None:
        t.end = time.perf_counter()
    if t.send == 0.0:
        t.send = t.end
    if not t.ok and t.error is None:
        t.error = "other"
    return t
