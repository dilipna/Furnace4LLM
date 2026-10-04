"""Minimal Server-Sent Events parsing for OpenAI-compatible streams.

OpenAI-style servers send one JSON object per ``data:`` line, terminated by
``data: [DONE]``. We parse line by line (not event by event) because every
production server we target emits single-line data fields; multi-line data
fields are joined for correctness anyway.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

DONE = object()


@dataclass
class ChunkInfo:
    """What a single streamed chunk contributes to timing/accounting."""

    has_output: bool  # carries generated content (text, reasoning, or tool-call delta)
    n_choices_text_chars: int
    usage: dict[str, Any] | None
    error: str | None
    finish_reason: str | None


class SSEDecoder:
    """Incremental decoder fed with lines from ``httpx.Response.aiter_lines()``."""

    def __init__(self) -> None:
        self._data: list[str] = []

    def feed(self, line: str) -> str | object | None:
        """Feed one line. Returns a complete data payload (str), DONE, or None."""
        if line == "":
            if not self._data:
                return None
            payload = "\n".join(self._data)
            self._data.clear()
            return DONE if payload.strip() == "[DONE]" else payload
        if line.startswith(":"):  # comment / keep-alive
            return None
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "data":
            # "[DONE]" is final; return it without waiting for the blank line.
            if value.strip() == "[DONE]" and not self._data:
                return DONE
            self._data.append(value)
        return None

    def flush(self) -> str | object | None:
        return self.feed("")


def inspect_chunk(payload: str) -> ChunkInfo:
    """Interpret one OpenAI chat.completion.chunk (or completion chunk) payload."""
    obj = json.loads(payload)
    if "error" in obj and obj.get("error"):
        err = obj["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return ChunkInfo(False, 0, None, msg or "server error", None)
    usage = obj.get("usage") or None
    has_output = False
    chars = 0
    finish = None
    for choice in obj.get("choices") or []:
        finish = choice.get("finish_reason") or finish
        delta = choice.get("delta")
        if delta is None:  # legacy /v1/completions
            text = choice.get("text") or ""
            if text:
                has_output = True
                chars += len(text)
            continue
        for key in ("content", "reasoning_content", "reasoning"):
            text = delta.get(key)
            if text:
                has_output = True
                chars += len(text)
        if delta.get("tool_calls"):
            has_output = True
    return ChunkInfo(has_output, chars, usage, None, finish)
