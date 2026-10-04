"""Reliability + Inference Blueprint."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from furnace.contracts.common import Priority


class Area(StrEnum):
    application = "application"
    reliability = "reliability"
    security = "security"
    observability = "observability"
    inference = "inference"


class Recommendation(BaseModel):
    id: UUID | None = None
    rule_id: str  # "rel.tool_approval_boundary"
    area: Area
    title: str
    why: str  # application-specific justification, built from facts
    evidence_ids: list[UUID] = Field(default_factory=list)
    priority: Priority
    confidence: float
    verification_method: str
    node_keys: list[str] = Field(default_factory=list)
    forge_action: str | None = None  # id of the Forge artifact generator, if installable


class Blueprint(BaseModel):
    schema_version: str = "furnace.blueprint/v1"
    scan_id: UUID
    recommendations: list[Recommendation] = Field(default_factory=list)
