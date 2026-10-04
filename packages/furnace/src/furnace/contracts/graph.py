"""Behavior-to-Code Reliability Graph contracts.

Nodes have *stable natural keys* (e.g. ``prompt:src/prompts.py::ANSWER_SYSTEM``)
so that graphs built from two commits can be diffed for PR impact analysis.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class NodeKind(StrEnum):
    workflow = "workflow"
    capability = "capability"
    route = "route"
    component = "component"  # file or symbol
    prompt = "prompt"
    model = "model"
    endpoint = "endpoint"
    serving_config = "serving_config"
    retriever = "retriever"
    tool = "tool"
    security_boundary = "security_boundary"
    config_key = "config_key"
    trace_cluster = "trace_cluster"
    failure_mode = "failure_mode"
    evaluator = "evaluator"
    benchmark = "benchmark"
    pull_request = "pull_request"
    repair = "repair"


class EdgeKind(StrEnum):
    implements = "implements"  # component -> capability, capability -> workflow
    routes_to = "routes_to"  # route -> component
    calls = "calls"  # component -> component
    uses_prompt = "uses_prompt"  # component -> prompt
    uses_model = "uses_model"  # component -> model
    served_by = "served_by"  # model -> endpoint
    configured_by = "configured_by"  # endpoint/retriever/... -> serving_config/config_key
    retrieves_via = "retrieves_via"  # component -> retriever
    invokes_tool = "invokes_tool"  # component -> tool
    guarded_by = "guarded_by"  # tool -> security_boundary
    observed_in = "observed_in"  # prompt/component -> trace_cluster
    may_fail_as = "may_fail_as"  # capability/tool/prompt -> failure_mode
    detected_by = "detected_by"  # failure_mode -> evaluator
    measured_by = "measured_by"  # endpoint/prompt/workflow -> benchmark
    touched_by = "touched_by"  # any -> pull_request
    repairs = "repairs"  # repair -> failure_mode
    depends_on = "depends_on"  # component -> component (import)


def node_key(kind: NodeKind, *parts: str) -> str:
    """Build a stable key: ``kind:part1::part2``. Parts must already be normalized
    (posix paths relative to repo root, symbol names, config key paths)."""
    return f"{kind.value}:" + "::".join(p.strip() for p in parts)


class GraphNode(BaseModel):
    id: UUID | None = None
    kind: NodeKind
    key: str
    label: str
    attrs: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    evidence_ids: list[UUID] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: UUID | None = None
    kind: EdgeKind
    src_key: str
    dst_key: str
    attrs: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    evidence_ids: list[UUID] = Field(default_factory=list)


class Graph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
