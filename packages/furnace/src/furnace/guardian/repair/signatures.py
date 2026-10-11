"""Regression signatures the repair loop supports.

A signature is a structural fact from the PR's impact analysis (the code graph of both
revisions), not an inference from a slow benchmark: a PR is handed to repair only when it
carries one, and the repair loop re-derives the same fact before it changes anything.

prefix_instability: a system message that was prefix-stable on the base revision starts
with a per-request value on the PR head (`dynamic_head` False -> True), so no two requests
share a cacheable prompt prefix. Its measured effect on this hardware is in
bench/results/2026-10-09-gate-warmup-v2/rq5.md.
"""

from __future__ import annotations

from furnace.contracts.guard import TouchedNode
from furnace.guardian.impact import ImpactResult

PREFIX_INSTABILITY = "prefix_instability"


def prefix_instability_node(impact: ImpactResult) -> TouchedNode | None:
    for t in impact.impact.touched:
        change = t.attr_changes.get("dynamic_head")
        if t.node_key.endswith("#system") and change is not None and tuple(change) == (False, True):
            return t
    return None


def supported_signatures(impact: ImpactResult) -> list[str]:
    return [PREFIX_INSTABILITY] if prefix_instability_node(impact) is not None else []
