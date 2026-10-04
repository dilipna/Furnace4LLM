"""Dependency signature catalog: package name -> what its presence suggests.

Presence of a dependency is weak evidence (it may be unused); extractors that
see the library actually *called* produce strong evidence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signature:
    category: str  # llm_sdk | llm_framework | serving | vector_store | retrieval | eval | tracing | web | retry | validation | testing
    provider: str | None = None
    note: str = ""


SIGNATURES: dict[str, Signature] = {
    # LLM SDKs / gateways
    "openai": Signature("llm_sdk", "openai_compatible"),
    "anthropic": Signature("llm_sdk", "anthropic"),
    "@anthropic-ai/sdk": Signature("llm_sdk", "anthropic"),
    "groq": Signature("llm_sdk", "groq"),
    "groq-sdk": Signature("llm_sdk", "groq"),
    "mistralai": Signature("llm_sdk", "mistral"),
    "google-generativeai": Signature("llm_sdk", "google"),
    "google-genai": Signature("llm_sdk", "google"),
    "@google/genai": Signature("llm_sdk", "google"),
    "cohere": Signature("llm_sdk", "cohere"),
    "ollama": Signature("llm_sdk", "ollama"),
    "litellm": Signature("llm_sdk", "litellm", "gateway/router"),
    "ai": Signature("llm_framework", None, "Vercel AI SDK"),
    "@ai-sdk/openai": Signature("llm_sdk", "openai_compatible"),
    "langchain": Signature("llm_framework"),
    "langchain-openai": Signature("llm_framework", "openai_compatible"),
    "langchain-community": Signature("llm_framework"),
    "@langchain/openai": Signature("llm_framework", "openai_compatible"),
    "llama-index": Signature("llm_framework"),
    "llama_index": Signature("llm_framework"),
    "instructor": Signature("validation", None, "structured LLM output"),
    "guardrails-ai": Signature("validation", None, "output guardrails"),
    # serving engines (when the app itself depends on them)
    "vllm": Signature("serving", "vllm"),
    "sglang": Signature("serving", "sglang"),
    "transformers": Signature("serving", "transformers"),
    # retrieval / vector stores
    "rank-bm25": Signature("retrieval", None, "BM25 keyword retrieval"),
    "rank_bm25": Signature("retrieval", None, "BM25 keyword retrieval"),
    "pgvector": Signature("vector_store", None, "pgvector"),
    "chromadb": Signature("vector_store", None, "Chroma"),
    "qdrant-client": Signature("vector_store", None, "Qdrant"),
    "pinecone": Signature("vector_store", None, "Pinecone"),
    "pinecone-client": Signature("vector_store", None, "Pinecone"),
    "faiss-cpu": Signature("vector_store", None, "FAISS"),
    "weaviate-client": Signature("vector_store", None, "Weaviate"),
    "sentence-transformers": Signature("retrieval", None, "embeddings"),
    # evals / tracing
    "ragas": Signature("eval"),
    "deepeval": Signature("eval"),
    "promptfoo": Signature("eval"),
    "langfuse": Signature("tracing", None, "Langfuse"),
    "langsmith": Signature("tracing", None, "LangSmith"),
    "opentelemetry-api": Signature("tracing", None, "OpenTelemetry"),
    "opentelemetry-sdk": Signature("tracing", None, "OpenTelemetry"),
    "@opentelemetry/api": Signature("tracing", None, "OpenTelemetry"),
    "arize-phoenix": Signature("tracing", None, "Phoenix"),
    # infra
    "fastapi": Signature("web", None, "FastAPI"),
    "flask": Signature("web", None, "Flask"),
    "django": Signature("web", None, "Django"),
    "express": Signature("web", None, "Express"),
    "next": Signature("web", None, "Next.js"),
    "tenacity": Signature("retry"),
    "backoff": Signature("retry"),
    "pytest": Signature("testing"),
    "vitest": Signature("testing"),
    "jest": Signature("testing"),
}

SERVING_IMAGES = {
    "vllm/vllm-openai": "vllm",
    "lmsysorg/sglang": "sglang",
    "ollama/ollama": "ollama",
    "ghcr.io/huggingface/text-generation-inference": "tgi",
}

# Well-known API hosts -> provider
API_HOSTS = {
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
    "api.groq.com": "groq",
    "openrouter.ai": "openrouter",
    "generativelanguage.googleapis.com": "google",
    "api.mistral.ai": "mistral",
    "api.together.xyz": "together",
    "api.fireworks.ai": "fireworks",
}

# Default local ports of serving engines (weak evidence)
ENGINE_PORTS = {11434: "ollama", 30000: "sglang"}


def normalize_dist_name(name: str) -> str:
    return (
        name.strip().lower().replace("_", "-") if not name.startswith("@") else name.strip().lower()
    )


def lookup(name: str) -> Signature | None:
    n = normalize_dist_name(name)
    return SIGNATURES.get(n) or SIGNATURES.get(name.strip().lower())
