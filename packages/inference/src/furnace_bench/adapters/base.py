"""Engine adapters: per-engine request extras, info probes, metrics mapping.

The request path is the OpenAI chat-completions API for every engine; adapters
only add what differs (output-length control, server metrics, version probes).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from furnace_bench.schema import BenchPlan, BenchTarget, LengthMode
from furnace_bench.telemetry.prom import parse_prometheus


class Adapter:
    name = "openai_compat"
    supports_ignore_eos = False
    # canonical name -> list of candidate raw metric names (first present wins)
    metric_map: dict[str, list[str]] = {}

    def __init__(self, target: BenchTarget) -> None:
        self.target = target

    # ---- urls -------------------------------------------------------------
    @property
    def base(self) -> str:
        return self.target.base_url.rstrip("/")

    @property
    def root(self) -> str:
        """Server root without the trailing /v1."""
        b = self.base
        return b[: -len("/v1")] if b.endswith("/v1") else b

    @property
    def chat_url(self) -> str:
        return f"{self.base}/chat/completions"

    @property
    def metrics_url(self) -> str | None:
        return self.target.metrics_url

    def headers(self) -> dict[str, str]:
        if self.target.api_key_env:
            key = os.environ.get(self.target.api_key_env)
            if key:
                return {"Authorization": f"Bearer {key}"}
        return {}

    # ---- request ----------------------------------------------------------
    def build_payload(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        plan: BenchPlan,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.target.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "stream": plan.stream,
            **extra,
        }
        if plan.stream:
            payload["stream_options"] = {"include_usage": True}
        payload.update(self.length_extras(max_tokens, plan))
        return payload

    def length_extras(self, max_tokens: int, plan: BenchPlan) -> dict[str, Any]:
        return {}

    def fixed_length_honored(self, plan: BenchPlan) -> bool:
        """Whether output lengths are actually pinned to max_tokens in this run."""
        return plan.length_mode == LengthMode.fixed and self.supports_ignore_eos

    # ---- probes -------------------------------------------------------------
    async def info(self, client: httpx.AsyncClient) -> dict[str, Any]:
        out: dict[str, Any] = {"engine": self.name}
        try:
            r = await client.get(f"{self.base}/models", headers=self.headers(), timeout=10)
            if r.status_code == 200:
                data = r.json().get("data") or []
                out["models"] = [m.get("id") for m in data]
                for m in data:
                    if m.get("id") == self.target.model and m.get("root"):
                        out["model_root"] = m["root"]
        except httpx.HTTPError:
            pass
        return out

    async def tokenize_count(self, client: httpx.AsyncClient, text: str) -> int | None:
        """Token count of `text` using the server's tokenizer, if the engine exposes one."""
        return None

    async def scrape(self, client: httpx.AsyncClient) -> dict[str, float]:
        if not self.metrics_url:
            return {}
        r = await client.get(self.metrics_url, timeout=5)
        r.raise_for_status()
        raw = parse_prometheus(r.text)
        out: dict[str, float] = {}
        for canonical, candidates in self.metric_map.items():
            for name in candidates:
                if name in raw:
                    out[canonical] = raw[name]
                    break
        return out


class OpenAICompatAdapter(Adapter):
    """Any OpenAI-compatible endpoint (commercial APIs, gateways, unknown servers)."""
