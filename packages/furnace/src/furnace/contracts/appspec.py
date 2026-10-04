"""AppSpec: reconstructed description of an existing LLM application.

Every leaf that could be wrong is a Claim. Lists of structural items (call
sites, tools, routes) carry their own claims for the fields that matter.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from furnace.contracts.common import Claim, Locator


class SideEffect(StrEnum):
    none = "none"
    read = "read"
    write = "write"
    external = "external"  # email, payments, third-party APIs


class ServingEngine(StrEnum):
    vllm = "vllm"
    sglang = "sglang"
    ollama = "ollama"
    tgi = "tgi"
    openai = "openai"
    anthropic = "anthropic"
    groq = "groq"
    openrouter = "openrouter"
    other_api = "other_api"
    unknown = "unknown"


class Route(BaseModel):
    key: str
    method: str
    path: str
    handler: str | None = None
    locator: Locator


class DynamicSegment(BaseModel):
    name: str  # interpolated variable / expression text
    token_offset: int | None = None  # approx position in rendered prompt; 0 = head
    char_offset: int


class PromptInfo(BaseModel):
    key: str
    locator: Locator
    static_chars: int
    static_tokens: int | None = None
    dynamic_segments: list[DynamicSegment] = Field(default_factory=list)
    # True if a dynamic segment appears before most of the static content,
    # which defeats prefix (KV) caching.
    dynamic_head: bool = False


class LLMCallSite(BaseModel):
    key: str
    locator: Locator
    api: str  # e.g. "openai.chat.completions.create"
    provider: Claim[str] | None = None
    model: Claim[str] | None = None
    streaming: Claim[bool] | None = None
    structured_output: bool = False
    tools_passed: bool = False
    params: dict[str, object] = Field(default_factory=dict)  # max_tokens, temperature, timeout
    prompt_keys: list[str] = Field(default_factory=list)
    endpoint_key: str | None = None
    has_timeout: bool = False


class Endpoint(BaseModel):
    key: str
    base_url_ref: str | None = None  # literal or "env:OPENAI_BASE_URL"
    engine: Claim[ServingEngine]
    serving_flags: dict[str, object] = Field(default_factory=dict)
    locator: Locator | None = None


class Retriever(BaseModel):
    key: str
    locator: Locator
    store: Claim[str]  # "bm25", "pgvector", "chroma", ...
    top_k: Claim[int] | None = None
    chunking: dict[str, object] = Field(default_factory=dict)


class Tool(BaseModel):
    key: str
    name: str
    locator: Locator
    side_effect: Claim[SideEffect]
    approval_gate: Claim[bool]


class Workflow(BaseModel):
    key: str
    name: str
    description: str
    steps: list[str] = Field(default_factory=list)
    route_keys: list[str] = Field(default_factory=list)
    capability_keys: list[str] = Field(default_factory=list)
    confidence: float


class Architecture(BaseModel):
    languages: dict[str, int] = Field(default_factory=dict)  # language -> file count
    frameworks: list[Claim[str]] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)  # compose services
    entrypoints: list[str] = Field(default_factory=list)
    deploy: list[str] = Field(default_factory=list)


class ExistingReliability(BaseModel):
    evals: list[Claim[str]] = Field(default_factory=list)
    tests: list[Claim[str]] = Field(default_factory=list)
    tracing: list[Claim[str]] = Field(default_factory=list)
    retries: list[Claim[str]] = Field(default_factory=list)
    timeouts: list[Claim[str]] = Field(default_factory=list)
    fallbacks: list[Claim[str]] = Field(default_factory=list)
    rate_limits: list[Claim[str]] = Field(default_factory=list)
    guardrails: list[Claim[str]] = Field(default_factory=list)


class RAGInfo(BaseModel):
    present: Claim[bool]
    retrievers: list[Retriever] = Field(default_factory=list)
    context_assembly: str | None = None


class Contradiction(BaseModel):
    subject_key: str
    predicate: str
    values: list[dict[str, object]]  # [{value, confidence, evidence_ids, method}]
    note: str


class AppSpec(BaseModel):
    schema_version: str = "furnace.appspec/v1"
    purpose: Claim[str] | None = None
    architecture: Architecture = Field(default_factory=Architecture)
    workflows: list[Workflow] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    llm_calls: list[LLMCallSite] = Field(default_factory=list)
    endpoints: list[Endpoint] = Field(default_factory=list)
    prompts: list[PromptInfo] = Field(default_factory=list)
    rag: RAGInfo | None = None
    tools: list[Tool] = Field(default_factory=list)
    reliability_existing: ExistingReliability = Field(default_factory=ExistingReliability)
    contradictions: list[Contradiction] = Field(default_factory=list)
