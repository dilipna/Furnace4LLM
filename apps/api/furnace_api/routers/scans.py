"""Scan endpoints. Public (anonymous) scans live in a shared `public` org and are
readable by their unguessable scan id; authenticated, private scans come with
GitHub login."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from furnace.db.models import (
    AppSpecRow,
    EvidenceRow,
    EvidenceSource,
    GraphEdgeRow,
    GraphNodeRow,
    Job,
    JobEvent,
    Org,
    Project,
    RecommendationRow,
    Scan,
)
from furnace.db.session import session_scope
from furnace.ingest.sources import SourceError, parse_github
from furnace.jobs import queue
from furnace.settings import get_settings
from furnace.storage.blob import get_blob_store, tenant_prefix
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from furnace_api.deps import db_session

router = APIRouter(prefix="/api")
DB = Annotated[AsyncSession, Depends(db_session)]
PUBLIC_ORG = "__public__"
MAX_UPLOAD_BYTES = 100 * 2**20

# Per-client-IP sliding window for anonymous scan creation (single API process).
_RATE: dict[str, deque[float]] = defaultdict(deque)
RATE_LIMIT, RATE_WINDOW_S = 10, 3600


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _RATE[ip]
    while hits and now - hits[0] > RATE_WINDOW_S:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(429, "Too many scans from this address; try again later or sign in.")
    hits.append(now)


async def _public_org(db: AsyncSession) -> Org:
    org = (await db.execute(select(Org).where(Org.name == PUBLIC_ORG))).scalar_one_or_none()
    if org is None:
        org = Org(name=PUBLIC_ORG)
        db.add(org)
        await db.flush()
    return org


class PublicScanIn(BaseModel):
    kind: Literal["github", "fixture"]
    value: str = Field(min_length=1, max_length=300)


class ScanRef(BaseModel):
    scan_id: str


async def _create_scan(
    db: AsyncSession,
    *,
    name: str,
    repo: str | None,
    source_kind: str,
    uri: str | None,
    source: dict[str, Any],
) -> Scan:
    org = await _public_org(db)
    project = Project(org_id=org.id, name=name, repo_full_name=repo, settings={})
    db.add(project)
    await db.flush()
    src = EvidenceSource(org_id=org.id, project_id=project.id, kind=source_kind, uri=uri, meta={})
    db.add(src)
    scan = Scan(org_id=org.id, project_id=project.id, status="queued", stats={})
    db.add(scan)
    await db.flush()
    if source.get("kind") == "zip":
        source["path"] = str(get_blob_store().path(source.pop("blob_key")))
    await queue.enqueue(
        db,
        queue="cpu",
        kind="scan.run",
        payload={"scan_id": str(scan.id), "source_id": str(src.id), "source": source},
        org_id=org.id,
        project_id=project.id,
        max_attempts=2,
    )
    return scan


@router.post("/public/scans", response_model=ScanRef, status_code=201)
async def create_public_scan(body: PublicScanIn, request: Request, db: DB) -> ScanRef:
    _rate_limit(request)
    if body.kind == "fixture":
        if get_settings().env != "dev":
            raise HTTPException(404, "not found")
        scan = await _create_scan(
            db,
            name=body.value,
            repo=None,
            source_kind="zip",
            uri=f"fixture:{body.value}",
            source={"kind": "fixture", "value": body.value},
        )
        return ScanRef(scan_id=str(scan.id))
    try:
        ref = parse_github(body.value)
    except SourceError as exc:
        raise HTTPException(422, str(exc)) from exc
    scan = await _create_scan(
        db,
        name=ref.full_name,
        repo=ref.full_name,
        source_kind="github",
        uri=f"https://github.com/{ref.full_name}",
        source={"kind": "github", "value": ref.full_name + (f"/tree/{ref.ref}" if ref.ref else "")},
    )
    return ScanRef(scan_id=str(scan.id))


@router.post("/public/scans/upload", response_model=ScanRef, status_code=201)
async def upload_scan(
    request: Request, db: DB, files: Annotated[list[UploadFile], File()]
) -> ScanRef:
    _rate_limit(request)
    zips = [f for f in files if (f.filename or "").lower().endswith(".zip")]
    if len(zips) != 1:
        raise HTTPException(
            422,
            "Upload one .zip of the project source. Screenshots, docs and traces can be added after the first scan.",
        )
    upload = zips[0]
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Upload larger than {MAX_UPLOAD_BYTES // 2**20} MB")
    org = await _public_org(db)
    blob_key = f"{tenant_prefix(org.id, 'uploads')}/{uuid.uuid4()}.zip"
    get_blob_store().put(blob_key, data)
    name = (upload.filename or "upload.zip").removesuffix(".zip")[:100]
    scan = await _create_scan(
        db,
        name=name,
        repo=None,
        source_kind="zip",
        uri=None,
        source={"kind": "zip", "blob_key": blob_key},
    )
    return ScanRef(scan_id=str(scan.id))


# ---------------------------------------------------------------------------- reads


async def _scan_or_404(db: AsyncSession, scan_id: str) -> Scan:
    try:
        sid = uuid.UUID(scan_id)
    except ValueError as exc:
        raise HTTPException(404, "scan not found") from exc
    scan = await db.get(Scan, sid)
    if scan is None:
        raise HTTPException(404, "scan not found")
    return scan


class ScanOut(BaseModel):
    id: str
    status: str
    project: str
    repo: str | None
    commit_sha: str | None
    stats: dict[str, Any]
    error: str | None
    created_at: str
    finished_at: str | None


@router.get("/scans/{scan_id}", response_model=ScanOut)
async def get_scan(scan_id: str, db: DB) -> ScanOut:
    scan = await _scan_or_404(db, scan_id)
    project = await db.get(Project, scan.project_id)
    assert project is not None
    return ScanOut(
        id=str(scan.id),
        status=scan.status,
        project=project.name,
        repo=project.repo_full_name,
        commit_sha=scan.commit_sha,
        stats=scan.stats,
        error=scan.error,
        created_at=scan.created_at.isoformat(),
        finished_at=scan.finished_at.isoformat() if scan.finished_at else None,
    )


async def _job_for_scan(db: AsyncSession, scan_id: uuid.UUID) -> Job | None:
    rows = await db.execute(
        select(Job)
        .where(Job.kind == "scan.run", Job.payload["scan_id"].astext == str(scan_id))
        .order_by(Job.created_at.desc())
    )
    return rows.scalars().first()


@router.get("/scans/{scan_id}/events")
async def scan_events(scan_id: str, db: DB) -> EventSourceResponse:
    scan = await _scan_or_404(db, scan_id)
    job = await _job_for_scan(db, scan.id)
    if job is None:
        raise HTTPException(404, "scan job not found")
    job_id = job.id

    async def stream() -> AsyncIterator[dict[str, str]]:
        last = 0
        idle_deadline = time.monotonic() + 600
        while time.monotonic() < idle_deadline:
            async with session_scope() as s:
                events: list[JobEvent] = await queue.events_since(s, job_id, last)
                current = await s.get(Scan, scan.id)
            for e in events:
                last = e.id
                yield {
                    "event": "progress",
                    "id": str(e.id),
                    "data": json.dumps(
                        {
                            "stage": e.stage,
                            "level": e.level,
                            "msg": e.msg,
                            "ts": e.ts.isoformat(),
                            "data": e.data,
                        }
                    ),
                }
            if current is not None and current.status in ("succeeded", "failed"):
                yield {
                    "event": "status",
                    "data": json.dumps({"status": current.status, "error": current.error}),
                }
                return
            await asyncio.sleep(0.5)

    return EventSourceResponse(stream())


@router.get("/scans/{scan_id}/blueprint")
async def get_blueprint(scan_id: str, db: DB) -> dict[str, Any]:
    scan = await _scan_or_404(db, scan_id)
    if scan.status != "succeeded":
        raise HTTPException(409, f"scan is {scan.status}")
    spec = await db.get(AppSpecRow, scan.id)
    recs = (
        (await db.execute(select(RecommendationRow).where(RecommendationRow.scan_id == scan.id)))
        .scalars()
        .all()
    )
    ev_rows = (
        (await db.execute(select(EvidenceRow).where(EvidenceRow.scan_id == scan.id)))
        .scalars()
        .all()
    )
    evidence = {
        str(e.id): {
            "locator": e.locator,
            "excerpt": e.excerpt,
            "extractor": e.extractor,
            "observation": e.observation,
        }
        for e in ev_rows
    }
    order = {"P0": 0, "P1": 1, "P2": 2}
    return {
        "scan": (await get_scan(scan_id, db)).model_dump(),
        "appspec": spec.spec if spec else None,
        "recommendations": [
            {
                "id": str(r.id),
                "rule_id": r.rule_id,
                "area": r.area,
                "title": r.title,
                "why": r.why,
                "priority": r.priority,
                "confidence": r.confidence,
                "verification_method": r.verification_method,
                "evidence_ids": [str(x) for x in r.evidence_ids],
                "node_keys": r.node_keys,
                "forge_action": r.forge_action,
            }
            for r in sorted(recs, key=lambda r: (order.get(r.priority, 9), -r.confidence))
        ],
        "evidence": evidence,
    }


@router.get("/scans/{scan_id}/graph")
async def get_graph(scan_id: str, db: DB) -> dict[str, Any]:
    scan = await _scan_or_404(db, scan_id)
    nodes = (
        (await db.execute(select(GraphNodeRow).where(GraphNodeRow.scan_id == scan.id)))
        .scalars()
        .all()
    )
    edges = (
        (await db.execute(select(GraphEdgeRow).where(GraphEdgeRow.scan_id == scan.id)))
        .scalars()
        .all()
    )
    return {
        "nodes": [
            {
                "key": n.key,
                "kind": n.kind,
                "label": n.label,
                "attrs": n.attrs,
                "confidence": n.confidence,
                "evidence_ids": [str(x) for x in n.evidence_ids],
            }
            for n in nodes
        ],
        "edges": [
            {
                "kind": e.kind,
                "src": e.src_key,
                "dst": e.dst_key,
                "confidence": e.confidence,
                "attrs": e.attrs,
            }
            for e in edges
        ],
    }
