"""Shared primitives: evidence, claims, provenance.

Every semantic fact Furnace states about an application is a `Claim`. A claim
always carries confidence, evidence ids, the method that produced it, and
whether it is a direct observation or an inference.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class Observation(StrEnum):
    direct_observation = "direct_observation"
    inference = "inference"


class Method(StrEnum):
    deterministic = "deterministic"
    llm = "llm"
    vlm = "vlm"
    trace = "trace"
    reconciled = "reconciled"


class ClaimStatus(StrEnum):
    supported = "supported"
    contested = "contested"  # >=2 surviving values with evidence; UI must show all
    unverified = "unverified"


class Claim(BaseModel, Generic[T]):
    value: T
    confidence: float = Field(ge=0.0, le=1.0)
    observation: Observation
    method: Method
    evidence_ids: list[UUID] = Field(default_factory=list)
    contradicted_by: list[UUID] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.supported
    # Alternative values in the same conflict group, shown verbatim to the user.
    alternatives: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceSourceKind(StrEnum):
    github = "github"
    zip = "zip"
    readme = "readme"
    text = "text"
    url = "url"
    openapi = "openapi"
    image = "image"
    video = "video"
    traces_jsonl = "traces_jsonl"
    otel = "otel"
    logs = "logs"
    endpoint = "endpoint"
    prompt = "prompt"
    conversation = "conversation"


class Locator(BaseModel):
    """Where in a source a piece of evidence lives. All fields optional by kind."""

    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    symbol: str | None = None
    url: str | None = None
    frame_ts: float | None = None  # video
    bbox: tuple[float, float, float, float] | None = None  # image region, normalized
    trace_ids: list[str] | None = None

    def short(self) -> str:
        if self.path and self.line_start:
            return f"{self.path}:{self.line_start}"
        return self.path or self.url or self.symbol or "?"


class Evidence(BaseModel):
    id: UUID
    source_id: UUID
    locator: Locator
    excerpt: str = Field(max_length=500)  # secret-redacted
    extractor: str  # e.g. "py_ast.openai_chat_call@1"
    observation: Observation


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
