"""FurnaceBench results (read-only) and the RQ2 human-labeling queue.

Every number the UI shows about Furnace itself comes from these files, which are
produced by `uv run poe bench-*` and committed under bench/results/<campaign>/.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from furnace.settings import get_settings
from pydantic import BaseModel

router = APIRouter(prefix="/api")

CAMPAIGN = re.compile(r"^\d{4}-\d{2}-\d{2}(-[a-z0-9-]+)?$")
SCENARIO = re.compile(r"^[a-z0-9_]+$")
RQ_FILES = {
    "rq1": "rq1.json",
    "rq1_first_scan": "rq1_first_scan.json",
    "rq1_set2_old_scanner": "rq1_set2_old_scanner.json",
    "rq2": "rq2.json",
    "rq3": "rq3.json",
    "rq4": "rq4/rq4.json",
    "rq5": "rq5.json",
}
W1 = "results/2026-10-04-f1-quality/workload-f1-traces-qwen05b.yaml"
LIVE_GUARD = "results/2026-10-04-guard"


def bench_dir() -> Path:
    configured = get_settings().bench_dir
    return configured if configured else Path(__file__).resolve().parents[4] / "bench"


def _read_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _campaign_dir(name: str) -> Path:
    if not CAMPAIGN.match(name):
        raise HTTPException(404, "unknown campaign")
    d = bench_dir() / "results" / name
    if not d.is_dir():
        raise HTTPException(404, "unknown campaign")
    return d


def _available(d: Path) -> list[str]:
    return [k for k, f in RQ_FILES.items() if (d / f).is_file()]


@router.get("/bench/campaigns")
def list_campaigns() -> list[dict[str, Any]]:
    root = bench_dir() / "results"
    out = []
    for d in sorted(root.iterdir() if root.is_dir() else [], reverse=True):
        if d.is_dir() and CAMPAIGN.match(d.name):
            avail = _available(d)
            if avail or (d / "REPORT.md").is_file():
                out.append(
                    {"name": d.name, "available": avail, "has_report": (d / "REPORT.md").is_file()}
                )
    return out


@router.get("/bench/campaigns/{name}")
def get_campaign(name: str) -> dict[str, Any]:
    d = _campaign_dir(name)

    def text(f: str) -> str | None:
        p = d / f
        return p.read_text(encoding="utf-8") if p.is_file() else None

    return {
        "name": name,
        "available": _available(d),
        "report_md": text("REPORT.md"),
        "notes_md": text("NOTES.md"),
        # dated corrections to a generated report; shown above it, never folded into it
        "corrections_md": text("CORRECTIONS.md"),
    }


@router.get("/bench/campaigns/{name}/{rq}")
def get_rq(name: str, rq: str) -> Any:
    d = _campaign_dir(name)
    f = RQ_FILES.get(rq)
    if f is None or not (d / f).is_file():
        raise HTTPException(404, f"{rq} has no results in {name}")
    data = _read_json(d / f)
    if rq.startswith("rq1"):
        for app in data.get("apps", []):
            app.pop("appspec", None)  # large; the scorer output is what the UI needs
    return data


@router.get("/bench/campaigns/{name}/rq3/{scenario}/check")
def get_rq3_check(name: str, scenario: str) -> dict[str, str]:
    d = _campaign_dir(name)
    p = d / "rq3" / f"{scenario}.targeted.check.md"
    if not SCENARIO.match(scenario) or not p.is_file():
        raise HTTPException(404, "unknown scenario")
    return {"markdown": p.read_text(encoding="utf-8")}


@router.get("/bench/workload")
def get_workload() -> dict[str, Any]:
    p = bench_dir() / W1
    if not p.is_file():
        raise HTTPException(404, "workload fingerprint not found")
    spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    return {"source": f"bench/{W1}", "spec": spec}


@router.get("/bench/guard-live")
def get_guard_live() -> list[dict[str, Any]]:
    """Single live Guard runs on F1 PR scenarios (2026-10-04), with their check-run text."""
    d = bench_dir() / LIVE_GUARD
    out = []
    for res in sorted(d.glob("*.results.json")) if d.is_dir() else []:
        name = res.name.removesuffix(".results.json")
        md = d / f"{name}.check.md"
        out.append(
            {
                "scenario": name,
                "results": _read_json(res),
                "check_md": md.read_text(encoding="utf-8") if md.is_file() else None,
            }
        )
    return out


# ------------------------------------------------------------------------- labeling


class LabelIn(BaseModel):
    id: str
    grounded: bool
    correct: bool | None = None
    notes: str = ""


def _labels_path() -> Path:
    return bench_dir() / "labels" / "f1_labels.jsonl"


def _jsonl(p: Path) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


@router.get("/labels/queue")
def label_queue() -> dict[str, Any]:
    queue = _jsonl(bench_dir() / "labels" / "f1_queue.jsonl")
    labels = {lab["id"]: lab for lab in _jsonl(_labels_path())}  # last label per id wins
    return {"items": queue, "labels": labels, "writable": get_settings().labels_writable}


@router.post("/labels", status_code=201)
def put_label(body: LabelIn) -> dict[str, Any]:
    if not get_settings().labels_writable:
        raise HTTPException(403, "labeling is disabled on this deployment")
    queue_ids = {q["id"] for q in _jsonl(bench_dir() / "labels" / "f1_queue.jsonl")}
    if body.id not in queue_ids:
        raise HTTPException(404, "unknown item")
    rec = {
        **body.model_dump(),
        "labeler": "web",
        "ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }
    rows = [r for r in _jsonl(_labels_path()) if r["id"] != body.id] + [rec]
    path = _labels_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    os.replace(tmp, path)  # atomic: a crash never leaves a half-written label file
    return rec
