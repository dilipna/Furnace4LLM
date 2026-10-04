"""The `scan.run` job: materialize source -> extract facts -> reconcile -> build the
AppSpec and graph -> Blueprint rules -> persist everything with provenance."""

from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import update

from furnace.blueprint.rules import run_rules
from furnace.code_intel.facts import FactSet
from furnace.db.models import (
    AppSpecRow,
    ClaimEvidence,
    ClaimRow,
    EvidenceRow,
    GraphEdgeRow,
    GraphNodeRow,
    RecommendationRow,
    Scan,
)
from furnace.db.session import session_scope
from furnace.ingest import sources
from furnace.jobs.worker import JobContext, handler
from furnace.reconstruction.build import Builder, Reconstruction, collect_facts
from furnace.reconstruction.reconcile import ClaimRec


async def _set_scan(scan_id: uuid.UUID, **values: Any) -> None:
    async with session_scope() as s:
        await s.execute(update(Scan).where(Scan.id == scan_id).values(**values))


async def _materialize(
    ctx: JobContext, source: dict[str, Any], workdir: Path
) -> tuple[Path, str | None, dict[str, Any]]:
    kind = source["kind"]
    if kind == "github":
        ref = sources.parse_github(source["value"])
        await ctx.emit("fetch", f"Resolving {ref.full_name} on GitHub")
        root, branch, sha, stats = await sources.materialize_github(ref, workdir)
        await ctx.emit(
            "fetch",
            f"Fetched {ref.full_name}@{sha[:7]} ({branch}): {stats.files} files",
            files=stats.files,
            bytes=stats.bytes,
        )
        return root, sha, {"repo": ref.full_name, "branch": branch, "skipped": stats.skipped[:20]}
    if kind == "zip":
        root, stats = sources.materialize_zip(Path(source["path"]), workdir)
        await ctx.emit(
            "fetch", f"Extracted upload: {stats.files} files", files=stats.files, bytes=stats.bytes
        )
        return root, None, {"skipped": stats.skipped[:20]}
    if kind == "fixture":
        root = sources.dev_fixture_root(source["value"])
        await ctx.emit("fetch", f"Using local fixture {source['value']}")
        return root, None, {"fixture": source["value"]}
    raise sources.SourceError(f"unsupported source kind {kind!r}")


async def persist(
    *,
    scan: Scan,
    source_id: uuid.UUID,
    facts: FactSet,
    fact_uuid: dict[str, uuid.UUID],
    builder: Builder,
    spec_json: dict[str, Any],
    graph: Any,
    recommendations: list[Any],
) -> None:
    org, project = scan.org_id, scan.project_id
    async with session_scope() as s:
        for f in facts.facts:
            s.add(
                EvidenceRow(
                    id=fact_uuid[f.id],
                    org_id=org,
                    scan_id=scan.id,
                    source_id=source_id,
                    locator=f.locator.model_dump(exclude_none=True)
                    | {"fact": f.id, "kind": f.kind, "key": f.key},
                    excerpt=f.excerpt[:500],
                    extractor=f.extractor,
                    observation=f.observation.value,
                )
            )
        await s.flush()
        claim_ids = [uuid.uuid4() for _ in builder.claims]
        for cid, c in zip(claim_ids, builder.claims, strict=True):
            s.add(_claim_row(cid, org, scan.id, c))
        await s.flush()  # claims must exist before claim_evidence rows reference them
        for cid, c in zip(claim_ids, builder.claims, strict=True):
            for fid in c.supports:
                if fid in fact_uuid:
                    s.add(
                        ClaimEvidence(claim_id=cid, evidence_id=fact_uuid[fid], stance="supports")
                    )
            for fid in c.contradicts:
                if fid in fact_uuid and fid not in c.supports:
                    s.add(
                        ClaimEvidence(
                            claim_id=cid, evidence_id=fact_uuid[fid], stance="contradicts"
                        )
                    )
        s.add(
            AppSpecRow(
                scan_id=scan.id,
                org_id=org,
                spec=spec_json,
                schema_version=spec_json["schema_version"],
            )
        )
        for n in graph.nodes:
            s.add(
                GraphNodeRow(
                    org_id=org,
                    project_id=project,
                    scan_id=scan.id,
                    kind=n.kind.value,
                    key=n.key,
                    label=n.label,
                    attrs=_jsonable(n.attrs),
                    confidence=n.confidence,
                    evidence_ids=n.evidence_ids,
                )
            )
        for e in graph.edges:
            s.add(
                GraphEdgeRow(
                    org_id=org,
                    project_id=project,
                    scan_id=scan.id,
                    kind=e.kind.value,
                    src_key=e.src_key,
                    dst_key=e.dst_key,
                    attrs=_jsonable(e.attrs),
                    confidence=e.confidence,
                    evidence_ids=e.evidence_ids,
                )
            )
        for r in recommendations:
            s.add(
                RecommendationRow(
                    org_id=org,
                    scan_id=scan.id,
                    rule_id=r.rule_id,
                    area=r.area.value,
                    title=r.title,
                    why=r.why,
                    evidence_ids=r.evidence_ids,
                    priority=r.priority.value,
                    confidence=r.confidence,
                    verification_method=r.verification_method,
                    node_keys=r.node_keys,
                    forge_action=r.forge_action,
                )
            )


def _claim_row(cid: uuid.UUID, org: uuid.UUID, scan_id: uuid.UUID, c: ClaimRec) -> ClaimRow:
    return ClaimRow(
        id=cid,
        org_id=org,
        scan_id=scan_id,
        subject_key=c.subject_key,
        predicate=c.predicate,
        value=_jsonable(c.value),
        confidence=c.confidence,
        method=c.method.value,
        observation=c.observation.value,
        status=c.status.value,
        conflict_group=c.conflict_group,
        rationale=c.rationale[:2000],
    )


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


@handler("scan.run")
async def run_scan(ctx: JobContext) -> dict[str, Any]:
    scan_id = uuid.UUID(ctx.payload["scan_id"])
    source_id = uuid.UUID(ctx.payload["source_id"])
    async with session_scope() as s:
        scan = await s.get(Scan, scan_id)
    if scan is None:
        raise LookupError(f"scan {scan_id} not found")
    await _set_scan(scan_id, status="running", started_at=datetime.now(UTC), error=None)
    workdir = sources.new_workdir()
    try:
        root, sha, meta = await _materialize(ctx, ctx.payload["source"], workdir)
        await ctx.emit("extract", "Inventorying files and parsing source")
        inv, facts = collect_facts(root)
        kinds: dict[str, int] = {}
        for f in facts.facts:
            kinds[f.kind] = kinds.get(f.kind, 0) + 1
        await ctx.emit(
            "extract",
            f"{len(inv.files)} files, {sum(inv.languages.values())} source/config files; "
            f"{kinds.get('llm_call', 0)} LLM call sites, {kinds.get('route', 0)} routes, "
            f"{kinds.get('prompt', 0) + kinds.get('system_message', 0)} prompts",
            facts=len(facts),
            kinds=kinds,
        )
        fact_uuid = {f.id: uuid.uuid4() for f in facts.facts}
        builder = Builder(inv, facts, fact_uuid)
        spec, graph = builder.build()
        contested = len(spec.contradictions)
        await ctx.emit(
            "reconcile",
            f"{len(builder.claims)} claims reconciled; {contested} contradiction{'s' if contested != 1 else ''} kept for review",
            claims=len(builder.claims),
            contradictions=contested,
        )
        await ctx.emit(
            "graph",
            f"Behavior-to-code graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges",
            nodes=len(graph.nodes),
            edges=len(graph.edges),
        )
        recs = run_rules(
            Reconstruction(
                inventory=inv, facts=facts, claims=builder.claims, appspec=spec, graph=graph
            ),
            fact_uuid,
        )
        by_p = {p: sum(1 for r in recs if r.priority.value == p) for p in ("P0", "P1", "P2")}
        await ctx.emit(
            "blueprint",
            f"{len(recs)} recommendations (P0 {by_p['P0']}, P1 {by_p['P1']}, P2 {by_p['P2']})",
            by_priority=by_p,
        )
        await persist(
            scan=scan,
            source_id=source_id,
            facts=facts,
            fact_uuid=fact_uuid,
            builder=builder,
            spec_json=spec.model_dump(mode="json"),
            graph=graph,
            recommendations=recs,
        )
        stats = {
            "files": len(inv.files),
            "languages": inv.languages,
            "facts": len(facts),
            "claims": len(builder.claims),
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "recommendations": len(recs),
            **meta,
        }
        await _set_scan(
            scan_id, status="succeeded", finished_at=datetime.now(UTC), commit_sha=sha, stats=stats
        )
        await ctx.emit("done", "Blueprint ready")
        return stats
    except sources.SourceError as exc:
        await _set_scan(scan_id, status="failed", finished_at=datetime.now(UTC), error=str(exc))
        await ctx.emit("error", str(exc), level="error")
        return {"error": str(exc)}  # user error: do not retry
    except Exception as exc:
        await _set_scan(
            scan_id,
            status="failed",
            finished_at=datetime.now(UTC),
            error="internal error during scan",
        )
        raise exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
