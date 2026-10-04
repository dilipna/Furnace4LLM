"""vLLM, SGLang and Ollama adapters."""

from __future__ import annotations

from typing import Any

import httpx

from furnace_bench.adapters.base import Adapter, OpenAICompatAdapter
from furnace_bench.schema import AdapterName, BenchPlan, BenchTarget, LengthMode


class VLLMAdapter(Adapter):
    name = "vllm"
    supports_ignore_eos = True
    # Names verified against vLLM 0.30 /metrics; older names kept as fallbacks.
    metric_map = {
        "running": ["vllm:num_requests_running"],
        "waiting": ["vllm:num_requests_waiting"],
        "kv_cache_usage": ["vllm:kv_cache_usage_perc", "vllm:gpu_cache_usage_perc"],
        "prefix_cache_queries": [
            "vllm:prefix_cache_queries_total",
            "vllm:prefix_cache_queries",
            "vllm:gpu_prefix_cache_queries_total",
        ],
        "prefix_cache_hits": [
            "vllm:prefix_cache_hits_total",
            "vllm:prefix_cache_hits",
            "vllm:gpu_prefix_cache_hits_total",
        ],
    }

    @property
    def metrics_url(self) -> str | None:
        return self.target.metrics_url or f"{self.root}/metrics"

    def length_extras(self, max_tokens: int, plan: BenchPlan) -> dict[str, Any]:
        if plan.length_mode == LengthMode.fixed:
            return {"ignore_eos": True}
        return {}

    async def info(self, client: httpx.AsyncClient) -> dict[str, Any]:
        out = await super().info(client)
        try:
            r = await client.get(f"{self.root}/version", timeout=10)
            if r.status_code == 200:
                out["engine_version"] = r.json().get("version")
        except (httpx.HTTPError, ValueError):
            pass
        return out

    async def tokenize_count(self, client: httpx.AsyncClient, text: str) -> int | None:
        try:
            r = await client.post(
                f"{self.root}/tokenize",
                json={"model": self.target.model, "prompt": text, "add_special_tokens": False},
                timeout=10,
            )
            if r.status_code == 200:
                return int(r.json()["count"])
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        return None


class SGLangAdapter(Adapter):
    name = "sglang"
    supports_ignore_eos = True
    # SGLang metrics require --enable-metrics. Names per SGLang docs; not yet
    # verified on a live server in this project (reported as not_exposed if absent).
    metric_map = {
        "running": ["sglang:num_running_reqs"],
        "waiting": ["sglang:num_queue_reqs"],
        "kv_cache_usage": ["sglang:token_usage"],
    }

    @property
    def metrics_url(self) -> str | None:
        return self.target.metrics_url or f"{self.root}/metrics"

    def length_extras(self, max_tokens: int, plan: BenchPlan) -> dict[str, Any]:
        if plan.length_mode == LengthMode.fixed:
            return {"ignore_eos": True}
        return {}

    async def info(self, client: httpx.AsyncClient) -> dict[str, Any]:
        out = await super().info(client)
        try:
            r = await client.get(f"{self.root}/get_server_info", timeout=10)
            if r.status_code == 200:
                out["engine_version"] = r.json().get("version")
        except (httpx.HTTPError, ValueError):
            pass
        return out


class OllamaAdapter(Adapter):
    """Ollama's OpenAI-compatible endpoint. No Prometheus metrics, no ignore_eos:
    in fixed-length mode max_tokens is only an upper bound, which the report notes."""

    name = "ollama"
    supports_ignore_eos = False

    async def info(self, client: httpx.AsyncClient) -> dict[str, Any]:
        out = await super().info(client)
        try:
            r = await client.get(f"{self.root}/api/version", timeout=10)
            if r.status_code == 200:
                out["engine_version"] = r.json().get("version")
        except (httpx.HTTPError, ValueError):
            pass
        return out


_ADAPTERS: dict[AdapterName, type[Adapter]] = {
    AdapterName.openai_compat: OpenAICompatAdapter,
    AdapterName.vllm: VLLMAdapter,
    AdapterName.sglang: SGLangAdapter,
    AdapterName.ollama: OllamaAdapter,
}


def make_adapter(target: BenchTarget) -> Adapter:
    return _ADAPTERS[target.adapter](target)
