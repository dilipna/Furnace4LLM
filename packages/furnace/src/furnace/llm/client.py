"""Thin OpenAI-compatible LLM client for Furnace's own reasoning (judges, synthesis).

Every supported provider (Groq, OpenRouter, Ollama, vLLM, OpenAI) speaks the
chat-completions API, so one client with a per-provider base URL is enough.
Keys are BYOK and read from the environment by name; they are never logged.

- JSON output: the reply must parse and validate against a JSON Schema; one
  corrective retry is attempted, then the call fails (never silently passes).
- Cache: responses keyed by a hash of (base_url, model, messages, params).
- Rate limit: async token bucket per client, for free-tier request limits.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import jsonschema

PROVIDERS: dict[str, tuple[str, str]] = {
    # name -> (base_url, api-key env var)
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", ""),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
}


class LLMError(Exception):
    pass


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    cache_hits: int = 0


class _TokenBucket:
    def __init__(self, per_minute: float) -> None:
        self.rate = per_minute / 60.0
        self.capacity = max(1.0, per_minute / 6)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def take(self) -> None:
        async with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) / self.rate)


@dataclass
class LLMClient:
    model: str
    base_url: str
    api_key: str | None = None
    requests_per_minute: float = 25.0
    cache_dir: Path | None = Path(".furnace-cache/llm")
    timeout_s: float = 60.0
    transport: httpx.AsyncBaseTransport | None = None  # injectable for tests
    usage: Usage = field(default_factory=Usage)

    def __post_init__(self) -> None:
        self._bucket = _TokenBucket(self.requests_per_minute)

    @classmethod
    def from_provider(cls, provider: str, model: str, **kw: Any) -> LLMClient:
        if provider not in PROVIDERS:
            raise LLMError(f"unknown provider {provider!r}")
        base, env = PROVIDERS[provider]
        key = os.environ.get(env) if env else None
        if env and not key:
            raise LLMError(f"{env} is not set (bring your own key for {provider})")
        return cls(model=model, base_url=base, api_key=key, **kw)

    def _cache_key(self, payload: dict[str, Any]) -> str:
        raw = json.dumps({"base": self.base_url, **payload}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = self._cache_key(payload)
        if self.cache_dir:
            hit = self.cache_dir / f"{key}.json"
            if hit.exists():
                self.usage.cache_hits += 1
                return json.loads(hit.read_text(encoding="utf-8"))
        await self._bucket.take()
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout_s, transport=self.transport
        ) as c:
            for attempt in range(3):
                r = await c.post("/chat/completions", json=payload, headers=headers)
                if r.status_code == 429 or r.status_code >= 500:
                    await asyncio.sleep(float(r.headers.get("retry-after", 2 ** (attempt + 1))))
                    continue
                if r.status_code >= 400:
                    raise LLMError(f"{r.status_code} from {self.base_url}: {r.text[:300]}")
                body = r.json()
                break
            else:
                raise LLMError(f"{self.base_url} unavailable after retries")
        u = body.get("usage") or {}
        self.usage.prompt_tokens += int(u.get("prompt_tokens") or 0)
        self.usage.completion_tokens += int(u.get("completion_tokens") or 0)
        self.usage.calls += 1
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(json.dumps(body), encoding="utf-8")
        return body

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        last_err = ""
        for attempt in range(2):
            body = await self._post(payload)
            text = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            try:
                data = json.loads(_strip_fences(text))
                jsonschema.validate(data, schema)
                return data
            except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
                last_err = exc.msg if isinstance(exc, json.JSONDecodeError) else exc.message
                if attempt == 0:
                    payload = {
                        **payload,
                        "messages": [
                            *messages,
                            {"role": "assistant", "content": text[:2000]},
                            {
                                "role": "user",
                                "content": f"That reply was invalid ({last_err}). Reply with only a JSON object matching the schema.",
                            },
                        ],
                    }
        raise LLMError(f"model did not return valid JSON after a retry: {last_err}")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()
