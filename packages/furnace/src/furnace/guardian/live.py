"""Structured Guard progress for live views.

A Guard run reports, in order: the impact analysis (which graph nodes the change touched,
what they affect, which checks that selects and why), then each selected check as it
starts and finishes, then the verdict. Events are plain dicts with a "type"; the runner
job stores them as job events and the UI replays them over SSE.
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from furnace_bench.schema import AdapterName, BenchTarget

from furnace.guardian.execute import GuardContext, prepare, run_items, selected_items, verdict
from furnace.guardian.impact import ImpactResult, TreeState, analyze_impact, analyze_tree
from furnace.guardian.report import check_run
from furnace.settings import get_settings

EventFn = Callable[[dict[str, Any]], None]
REPO_ROOT = Path(__file__).resolve().parents[5]


def impact_event(impact: ImpactResult, head: TreeState) -> dict[str, Any]:
    """The impact analysis plus the subgraph it walked (touched, affected and path nodes)."""
    imp = impact.impact
    touched = {t.node_key: str(t.via) for t in imp.touched}
    keys = set(imp.affected_keys) | set(touched)
    for s in imp.selected:
        keys |= set(s.path)
    return {
        "type": "impact",
        "categories": sorted(impact.categories),
        "touched": [{"key": k, "via": v} for k, v in touched.items()],
        "affected": sorted(imp.affected_keys),
        "selected": [{"key": s.key, "reason": s.reason, "path": s.path} for s in imp.selected],
        "skipped": [{"key": s.key, "reason": s.reason} for s in imp.skipped],
        "full_suite_size": imp.full_suite_size,
        "fell_back_to_full": imp.fell_back_to_full,
        "changed": [c.path for c in imp.changed],
        "nodes": [
            {"key": n.key, "kind": str(n.kind), "label": n.label}
            for n in head.graph.nodes
            if n.key in keys
        ],
        "edges": [
            {"src": e.src_key, "dst": e.dst_key, "kind": str(e.kind)}
            for e in head.graph.edges
            if e.src_key in keys and e.dst_key in keys
        ],
    }


def _fixtures() -> Path:
    return get_settings().fixtures_dir or REPO_ROOT / "fixtures"


def _scenarios_module() -> Any:
    d = str(_fixtures() / "scenarios")
    if d not in sys.path:
        sys.path.insert(0, d)
    return importlib.import_module("f1_scenarios"), importlib.import_module("f1_suite")


def scenario_names() -> list[str]:
    scen, _ = _scenarios_module()
    return [s.name for s in scen.SCENARIOS]


def run_local_guard(scenario: str, emit: EventFn, *, with_endpoint: bool = True) -> dict[str, Any]:
    """Guard the F1 fixture PR scenario `scenario` locally (base = F1 main), reporting live.

    The same impact analysis and executors as `gh-guard`, without GitHub: used for the
    live demo view and when no GitHub App is configured.
    """
    scen, suite_mod = _scenarios_module()
    s = next((x for x in scen.SCENARIOS if x.name == scenario), None)
    if s is None:
        raise ValueError(f"unknown scenario {scenario!r}")
    suite = suite_mod.F1_SUITE
    settings = get_settings()
    facts = json.loads((scen.F1 / "docs" / "facts.json").read_text(encoding="utf-8"))
    questions = [f["question"] for f in facts]
    target = (
        BenchTarget(
            adapter=AdapterName.vllm,
            base_url=settings.lab_base_url,
            model=settings.lab_model,
            label="lab vLLM",
        )
        if with_endpoint
        else None
    )
    t_start = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="furnace-guard-live-"))
    try:
        emit({"type": "phase", "phase": "prepare", "msg": f"{s.name}: {s.description}"})
        base_root = scen.materialize(None, tmp / "base")
        head_root = scen.materialize(s, tmp / "head")
        t0 = time.monotonic()
        head_state = analyze_tree(head_root)
        impact = analyze_impact(analyze_tree(base_root), head_state, suite)
        ev = impact_event(impact, head_state)
        ev["seconds"] = round(time.monotonic() - t0, 2)
        emit(ev)
        items = selected_items(impact, suite)
        work, base, head = prepare(base_root, head_root)
        try:
            ctx = GuardContext(
                base=base,
                head=head,
                questions=questions,
                target=target,
                max_prompt_tokens=settings.guard_max_prompt_tokens or 4096 - 256,
            )
            results = run_items(items, ctx, on_event=emit)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        cr = check_run(impact, results, verdict(results))
        out = {
            "type": "verdict",
            "conclusion": cr["conclusion"],
            "title": cr["title"],
            "seconds": round(time.monotonic() - t_start, 1),
            "executed": len(results),
            "suite_size": len(suite),
        }
        emit(out)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
