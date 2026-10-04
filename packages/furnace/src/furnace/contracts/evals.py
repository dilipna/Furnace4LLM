"""Failure modes, evaluators and calibration."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class FailureCategory(StrEnum):
    quality = "quality"
    security = "security"
    performance = "performance"
    reliability = "reliability"


class FailureOrigin(StrEnum):
    bootstrap_appspec = "bootstrap_appspec"  # top-down from reconstruction
    trace_analysis = "trace_analysis"  # bottom-up from observed failures
    human = "human"


class FailureMode(BaseModel):
    id: UUID | None = None
    key: str  # "fm:ungrounded_answer"
    name: str
    description: str
    category: FailureCategory
    origin: FailureOrigin
    severity: int = Field(ge=1, le=3, default=2)  # 1 = highest
    capability_key: str | None = None
    example_item_ids: list[UUID] = Field(default_factory=list)


class EvaluatorKind(StrEnum):
    deterministic = "deterministic"
    llm_judge = "llm_judge"
    perf_gate = "perf_gate"


class EvaluatorStatus(StrEnum):
    draft = "draft"
    calibrating = "calibrating"  # results shown as advisory only
    trusted = "trusted"
    retired = "retired"


class Calibration(BaseModel):
    n: int
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float | None
    recall: float | None
    f1: float | None
    tpr: float | None
    tnr: float | None
    label_set_version: str
    split: str = "test"


class Evaluator(BaseModel):
    id: UUID | None = None
    key: str  # "ev:citation_required"
    version: int = 1
    failure_mode_key: str
    kind: EvaluatorKind
    # deterministic: {"check": "citation_required", "params": {...}}
    # llm_judge: {"prompt": "...", "model": "...", "provider": "...", "temperature": 0}
    # perf_gate: {"metric": "ttft_ms.p95", "level": 8, "budget_pct": 25}
    spec: dict[str, Any]
    content_hash: str
    status: EvaluatorStatus = EvaluatorStatus.draft
    calibration: Calibration | None = None


class Verdict(StrEnum):
    PASS = "PASS"  # noqa: S105 - verdict label, not a password
    FAIL = "FAIL"
    ERROR = "ERROR"  # evaluator could not run
    SKIP = "SKIP"
