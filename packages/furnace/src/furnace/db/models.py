"""SQLAlchemy models. Tenancy: every project-scoped row carries org_id so that
repositories can enforce org scoping with a single predicate.

Specs and summaries are JSONB; anything we filter or join on is a column.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _fk(target: str, *, nullable: bool = False, ondelete: str = "CASCADE") -> Mapped[Any]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable, index=True
    )


# ---------------------------------------------------------------- tenancy / auth


class Org(Base):
    __tablename__ = "orgs"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    github_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    login: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class Membership(Base):
    __tablename__ = "memberships"
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), default="owner")


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    name: Mapped[str] = mapped_column(String(200))
    repo_full_name: Mapped[str | None] = mapped_column(String(300), index=True)
    default_branch: Mapped[str | None] = mapped_column(String(200))
    github_installation_id: Mapped[int | None] = mapped_column(BigInteger)
    pr_write_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    public_share_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class Secret(Base):
    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    name: Mapped[str] = mapped_column(String(100))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    last4: Mapped[str] = mapped_column(String(4))
    created_at: Mapped[datetime] = _created()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID | None] = _fk("orgs.id", nullable=True, ondelete="SET NULL")
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(300))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- evidence / scan


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    kind: Mapped[str] = mapped_column(String(30))
    uri: Mapped[str | None] = mapped_column(Text)  # github ref, url, etc.
    blob_key: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    llm_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class EvidenceRow(Base):
    __tablename__ = "evidence"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    scan_id: Mapped[uuid.UUID] = _fk("scans.id")
    source_id: Mapped[uuid.UUID] = _fk("evidence_sources.id")
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB)
    excerpt: Mapped[str] = mapped_column(String(500))
    extractor: Mapped[str] = mapped_column(String(100))
    observation: Mapped[str] = mapped_column(String(30))


class ClaimRow(Base):
    __tablename__ = "claims"
    __table_args__ = (Index("ix_claims_subject_predicate", "scan_id", "subject_key", "predicate"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    scan_id: Mapped[uuid.UUID] = _fk("scans.id")
    subject_key: Mapped[str] = mapped_column(Text)
    predicate: Mapped[str] = mapped_column(String(60))
    value: Mapped[Any] = mapped_column(JSONB)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(20))
    observation: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="supported")
    conflict_group: Mapped[str | None] = mapped_column(String(64), index=True)
    rationale: Mapped[str | None] = mapped_column(Text)


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
    stance: Mapped[str] = mapped_column(String(12), default="supports")
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class AppSpecRow(Base):
    __tablename__ = "app_specs"
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), primary_key=True
    )
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[str] = mapped_column(String(40))


class WorkloadSpecRow(Base):
    __tablename__ = "workload_specs"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    scan_id: Mapped[uuid.UUID | None] = _fk("scans.id", nullable=True, ondelete="SET NULL")
    name: Mapped[str] = mapped_column(String(100))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(30))
    synthetic: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- graph


class GraphNodeRow(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (UniqueConstraint("scan_id", "key"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    scan_id: Mapped[uuid.UUID] = _fk("scans.id")
    kind: Mapped[str] = mapped_column(String(30), index=True)
    key: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)


class GraphEdgeRow(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (Index("ix_graph_edges_scan_src", "scan_id", "src_key"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    scan_id: Mapped[uuid.UUID] = _fk("scans.id")
    kind: Mapped[str] = mapped_column(String(30))
    src_key: Mapped[str] = mapped_column(Text)
    dst_key: Mapped[str] = mapped_column(Text)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)


class RecommendationRow(Base):
    __tablename__ = "recommendations"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    scan_id: Mapped[uuid.UUID] = _fk("scans.id")
    rule_id: Mapped[str] = mapped_column(String(80))
    area: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    priority: Mapped[str] = mapped_column(String(2))
    confidence: Mapped[float] = mapped_column(Float)
    verification_method: Mapped[str] = mapped_column(Text)
    node_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    forge_action: Mapped[str | None] = mapped_column(String(80))


# ---------------------------------------------------------------- evals


class FailureModeRow(Base):
    __tablename__ = "failure_modes"
    __table_args__ = (UniqueConstraint("project_id", "key"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(30))
    severity: Mapped[int] = mapped_column(Integer, default=2)
    capability_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class EvaluatorRow(Base):
    __tablename__ = "evaluators"
    __table_args__ = (UniqueConstraint("project_id", "key", "version"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    failure_mode_id: Mapped[uuid.UUID | None] = _fk(
        "failure_modes.id", nullable=True, ondelete="SET NULL"
    )
    key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(20))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    calibration: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()


class EvalDataset(Base):
    __tablename__ = "eval_datasets"
    __table_args__ = (UniqueConstraint("project_id", "name", "version"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(30))  # bootstrap_synthetic | trace_sample | regression
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _created()


class EvalItem(Base):
    __tablename__ = "eval_items"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    dataset_id: Mapped[uuid.UUID] = _fk("eval_datasets.id")
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    expected: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    trace_ref: Mapped[str | None] = mapped_column(Text)
    split: Mapped[str | None] = mapped_column(String(10))  # train | dev | test
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class HumanLabel(Base):
    __tablename__ = "human_labels"
    __table_args__ = (UniqueConstraint("item_id", "failure_mode_id", "labeler"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    item_id: Mapped[uuid.UUID] = _fk("eval_items.id")
    failure_mode_id: Mapped[uuid.UUID] = _fk("failure_modes.id")
    verdict: Mapped[str] = mapped_column(String(4))  # PASS | FAIL
    labeler: Mapped[str] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    dataset_id: Mapped[uuid.UUID | None] = _fk(
        "eval_datasets.id", nullable=True, ondelete="SET NULL"
    )
    target: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class EvalResult(Base):
    __tablename__ = "eval_results"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    run_id: Mapped[uuid.UUID] = _fk("eval_runs.id")
    item_id: Mapped[uuid.UUID] = _fk("eval_items.id")
    evaluator_id: Mapped[uuid.UUID] = _fk("evaluators.id")
    verdict: Mapped[str] = mapped_column(String(5))
    reason: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)


# ---------------------------------------------------------------- inference


class EndpointRow(Base):
    __tablename__ = "endpoints"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    name: Mapped[str] = mapped_column(String(100))
    adapter: Mapped[str] = mapped_column(String(20))
    base_url: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(200))
    metrics_url: Mapped[str | None] = mapped_column(Text)
    secret_name: Mapped[str | None] = mapped_column(String(100))  # -> secrets.name
    runner_only: Mapped[bool] = mapped_column(Boolean, default=True)  # private network endpoint
    created_at: Mapped[datetime] = _created()


class BenchRun(Base):
    __tablename__ = "bench_runs"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    workload_spec_id: Mapped[uuid.UUID | None] = _fk(
        "workload_specs.id", nullable=True, ondelete="SET NULL"
    )
    target: Mapped[dict[str, Any]] = mapped_column(JSONB)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB)
    env: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    raw_blob: Mapped[str | None] = mapped_column(Text)
    telemetry_blob: Mapped[str | None] = mapped_column(Text)
    report_md_blob: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(String(40))  # baseline | pr_gate | optimize | adhoc
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- forge / guard / repair


class ForgeRun(Base):
    __tablename__ = "forge_runs"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    scan_id: Mapped[uuid.UUID | None] = _fk("scans.id", nullable=True, ondelete="SET NULL")
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB)
    patch_blob: Mapped[str | None] = mapped_column(Text)
    validation: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    pr_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class PRImpactRow(Base):
    __tablename__ = "pr_impacts"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    base_sha: Mapped[str] = mapped_column(String(64))
    head_sha: Mapped[str] = mapped_column(String(64))
    impact: Mapped[dict[str, Any]] = mapped_column(JSONB)  # contracts.guard.PRImpact
    check_run_id: Mapped[int | None] = mapped_column(BigInteger)
    verdict: Mapped[str | None] = mapped_column(String(20))  # success | neutral | failure
    results: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_at: Mapped[datetime] = _created()


class RepairAttemptRow(Base):
    __tablename__ = "repair_attempts"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _fk("orgs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    pr_impact_id: Mapped[uuid.UUID | None] = _fk(
        "pr_impacts.id", nullable=True, ondelete="SET NULL"
    )
    attempt: Mapped[dict[str, Any]] = mapped_column(JSONB)  # contracts.guard.RepairAttempt
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    created_at: Mapped[datetime] = _created()


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    delivery_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event: Mapped[str] = mapped_column(String(50))
    received_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- jobs


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_claim", "queue", "status", "run_after"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID | None] = _fk("orgs.id", nullable=True)
    project_id: Mapped[uuid.UUID | None] = _fk("projects.id", nullable=True)
    queue: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_by: Mapped[str | None] = mapped_column(String(100))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobEvent(Base):
    __tablename__ = "job_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = _fk("jobs.id")
    ts: Mapped[datetime] = _created()
    stage: Mapped[str] = mapped_column(String(60))
    level: Mapped[str] = mapped_column(String(10), default="info")
    msg: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Runner(Base):
    __tablename__ = "runners"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    queues: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # gpu, docker, ...
    last_seen: Mapped[datetime] = _created()
