"""Forge plans, PR impact analysis and repair attempts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChangeType(StrEnum):
    add_file = "add_file"
    codemod = "codemod"  # evalability refactor of existing code


class ForgeChange(BaseModel):
    path: str
    change_type: ChangeType
    reason: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    target: str  # evaluator / failure mode / perf target key this change serves
    risk: str
    recommendation_rule_id: str | None = None


class ForgePlan(BaseModel):
    changes: list[ForgeChange] = Field(default_factory=list)


class Hunk(BaseModel):
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int


class ChangedFile(BaseModel):
    path: str
    status: str  # added | modified | removed | renamed
    hunks: list[Hunk] = Field(default_factory=list)


class TouchVia(StrEnum):
    file = "file"
    symbol = "symbol"
    config_key = "config_key"
    prompt_segment = "prompt_segment"
    dependency = "dependency"


class TouchedNode(BaseModel):
    node_key: str
    via: TouchVia
    attr_changes: dict[str, tuple[Any, Any]] = Field(default_factory=dict)  # attr -> (base, head)


class Selection(BaseModel):
    key: str
    kind: str  # evaluator | benchmark | check
    reason: str
    path: list[str] = Field(default_factory=list)  # graph path that justified selection


class PRImpact(BaseModel):
    pr_number: int
    base_sha: str
    head_sha: str
    changed: list[ChangedFile] = Field(default_factory=list)
    touched: list[TouchedNode] = Field(default_factory=list)
    affected_keys: list[str] = Field(default_factory=list)
    selected: list[Selection] = Field(default_factory=list)
    skipped: list[Selection] = Field(default_factory=list)
    full_suite_size: int = 0
    fell_back_to_full: bool = False
    policy_version: str = "v1"


class RepairStatus(StrEnum):
    created = "created"
    reproducing = "reproducing"
    repro_failed = "repro_failed"  # could not produce a failing test -> repair is forbidden
    reproduced = "reproduced"
    localizing = "localizing"
    generating = "generating"
    validating = "validating"
    verified = "verified"
    rejected = "rejected"  # no candidate passed validation
    pr_opened = "pr_opened"


class RegressionTest(BaseModel):
    path: str
    kind: str  # pytest_deterministic | perf_regression
    content_hash: str


class Repro(BaseModel):
    head_fails: bool
    base_passes: bool
    logs: str = ""


class LocalizationCandidate(BaseModel):
    node_key: str
    file: str
    hunk: Hunk | None = None
    score: float
    reasons: list[str] = Field(default_factory=list)


class RepairCandidate(BaseModel):
    strategy: str  # "rule:prefix_stability.move_dynamic_to_suffix" | "llm:<model>"
    diff: str
    sandbox_run_id: str | None = None
    results: dict[str, Any] = Field(default_factory=dict)
    verdict: str | None = None  # pass | fail | error


class RepairAttempt(BaseModel):
    id: UUID | None = None
    trigger: dict[str, Any]
    failure_mode_key: str | None = None
    regression_test: RegressionTest | None = None
    repro: Repro | None = None
    localization: list[LocalizationCandidate] = Field(default_factory=list)
    candidates: list[RepairCandidate] = Field(default_factory=list)
    selected: int | None = None
    draft_pr_url: str | None = None
    status: RepairStatus = RepairStatus.created
