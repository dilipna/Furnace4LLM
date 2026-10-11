"""Regression signatures the repair loop supports.

A signature is a structural fact from the PR's impact analysis (the code graph of both
revisions), not an inference from a slow benchmark: a PR is handed to repair only when it
carries one, and the repair loop re-derives the same fact before it changes anything.

prefix_instability: a system message that was prefix-stable on the base revision starts
with a per-request value on the PR head (`dynamic_head` False -> True), so no two requests
share a cacheable prompt prefix. Its measured effect on this hardware is in
bench/results/2026-10-09-gate-warmup-v2/rq5.md. Impact analysis uses the same predicate
(guardian.impact.lost_stable_prefix) to select the perf benchmarks.
"""

from __future__ import annotations

from furnace.contracts.guard import TouchedNode
from furnace.guardian.impact import ImpactResult, lost_stable_prefix

PREFIX_INSTABILITY = "prefix_instability"


def prefix_instability_node(impact: ImpactResult) -> TouchedNode | None:
    return next((t for t in impact.impact.touched if lost_stable_prefix(t)), None)


def supported_signatures(impact: ImpactResult) -> list[str]:
    return [PREFIX_INSTABILITY] if prefix_instability_node(impact) is not None else []
