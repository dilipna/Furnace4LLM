"""PR impact analysis on the Behavior-to-Code graph.

base tree + head tree
  -> changed files and line hunks
  -> touched graph nodes (fact line spans intersecting hunks, attribute diffs,
     added/removed nodes)
  -> change categories (prompt, retrieval_config, serving_config, tool, ...)
  -> affected nodes (touched + their ancestors: components, capabilities, workflows)
  -> selected suite items (bound to an affected node and triggered by a category),
     each with the graph path that justified it; everything else is skipped with a reason.

Conservative fallback: an application-code change that maps to no fact selects
the full suite, and says why.
"""

from __future__ import annotations

import difflib
import fnmatch
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from furnace.code_intel.facts import Fact
from furnace.code_intel.inventory import Inventory
from furnace.contracts.graph import Graph, NodeKind
from furnace.contracts.guard import ChangedFile, Hunk, PRImpact, Selection, TouchedNode, TouchVia
from furnace.reconstruction.build import Builder, collect_facts

# Attributes that are positional, not semantic: changes there are not behavior changes.
POSITIONAL_ATTRS = {"line", "path"}
NON_APP_PREFIXES = ("tests/", "test/", "scripts/", "docs/", ".github/")
DEPENDENCY_FILES = re.compile(
    r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|setup\.cfg|setup\.py|package\.json|poetry\.lock|uv\.lock|package-lock\.json|pnpm-lock\.yaml)$"
)
LLM_SDK_NAMES = re.compile(
    r"(?i)\b(openai|anthropic|litellm|langchain|llama[-_]index|vllm|sglang|ollama|transformers|groq|tiktoken|tokenizers)\b"
)
IGNORABLE_LINE = re.compile(r"^\s*(#.*|import\s.+|from\s+\S+\s+import\s.+|)$")


@dataclass
class SuiteItem:
    key: str  # "check:citation_required", "bench:chat_perf_gate", "unit:tests/test_prompts.py"
    kind: str  # unit | check | judge | security | benchmark
    binds: list[str]  # node-key glob patterns this item exercises
    triggers: set[str]  # change categories that make it relevant ("*" = any)
    always: bool = False
    cost: dict[str, float] = field(default_factory=dict)  # seconds / llm_tokens / gpu_seconds


@dataclass
class TreeState:
    root: Path
    inventory: Inventory
    facts: list[Fact]
    graph: Graph


def analyze_tree(root: Path) -> TreeState:
    inv, fs = collect_facts(root)
    b = Builder(inv, fs)
    _, graph = b.build()
    return TreeState(root=root, inventory=inv, facts=fs.facts, graph=graph)


# ---------------------------------------------------------------------------- diff


def diff_trees(base: TreeState, head: TreeState) -> list[ChangedFile]:
    bfiles = {f.path: f for f in base.inventory.files}
    hfiles = {f.path: f for f in head.inventory.files}
    changed: list[ChangedFile] = []
    for path in sorted(set(bfiles) | set(hfiles)):
        b, h = bfiles.get(path), hfiles.get(path)
        if b and h and b.sha256 == h.sha256:
            continue
        status = "added" if b is None else "removed" if h is None else "modified"
        hunks: list[Hunk] = []
        if b is not None and h is not None and not (b.binary or h.binary):
            a_lines = base.inventory.read(b).splitlines()
            b_lines = head.inventory.read(h).splitlines()
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, a_lines, b_lines, autojunk=False
            ).get_opcodes():
                if tag != "equal":
                    hunks.append(
                        Hunk(
                            old_start=i1 + 1, old_lines=i2 - i1, new_start=j1 + 1, new_lines=j2 - j1
                        )
                    )
        changed.append(ChangedFile(path=path, status=status, hunks=hunks))
    return changed


def _overlaps(start: int | None, end: int | None, lo: int, n: int) -> bool:
    if start is None:
        return False
    end = end or start
    if n == 0:
        # Zero-length side of a hunk (lines only inserted or only deleted): the change sits
        # *before* line `lo` on this side, so it is inside the span only if start < lo <= end.
        # (An insertion right after a function body is module-level code, not that function.)
        return start < lo <= end
    return start <= lo + n - 1 and lo <= end


def _touched_by_hunks(
    facts: list[Fact], changed: dict[str, ChangedFile], side: str
) -> dict[str, list[Fact]]:
    out: dict[str, list[Fact]] = {}
    for f in facts:
        cf = changed.get(f.locator.path or "")
        if cf is None:
            continue
        if cf.status in ("added", "removed"):
            hit = (cf.status == "added") == (side == "head")
        else:
            hit = any(
                _overlaps(
                    f.locator.line_start,
                    f.locator.line_end,
                    h.new_start if side == "head" else h.old_start,
                    h.new_lines if side == "head" else h.old_lines,
                )
                for h in cf.hunks
            )
        if hit:
            out.setdefault(f.key, []).append(f)
    return out


# ---------------------------------------------------------------------------- categories


def categorize(node_key: str, kind: NodeKind | None, attrs_changed: dict[str, Any]) -> set[str]:
    if kind == NodeKind.prompt:
        return {"prompt"}
    if kind == NodeKind.config_key:
        if ".--" in node_key:
            return {"serving_config"}
        if re.search(r"retriev|top_k|context|chunk|rerank", node_key, re.I):
            return {"retrieval_config"}
        if re.search(r"generation|max_tokens|temperature|top_p", node_key, re.I):
            return {"generation_config"}
        return {"config"}
    if kind == NodeKind.serving_config:
        return {"serving_config"}
    if kind in (NodeKind.tool, NodeKind.security_boundary):
        return {"tool"}
    if kind == NodeKind.model:
        return {"model"}
    if kind == NodeKind.retriever:
        return {"retrieval"}
    if kind == NodeKind.endpoint:
        return {"endpoint"}
    if kind == NodeKind.route:
        return {"route"}
    if kind == NodeKind.component:
        return {"llm_call"} if "#llm" in node_key else {"code"}
    return set()


# ---------------------------------------------------------------------------- traversal


def _ancestors(graph: Graph, starts: set[str]) -> dict[str, list[str]]:
    """Walk *up* from touched nodes: to whatever uses them (reverse edges: callers,
    routes, configured components) and forward along `implements` to the capabilities
    and workflows they belong to. Never walk from a capability/workflow back down to
    its other members: a change to one member does not affect its siblings.
    Returns {node: path from a touched node}."""
    kinds = {n.key: n.kind for n in graph.nodes}
    parents: dict[str, list[str]] = {}
    implements: dict[str, list[str]] = {}
    for e in graph.edges:
        if e.kind.value == "implements":
            implements.setdefault(e.src_key, []).append(e.dst_key)
        else:
            parents.setdefault(e.dst_key, []).append(e.src_key)
    paths: dict[str, list[str]] = {s: [s] for s in starts}
    q = deque(starts)
    while q:
        n = q.popleft()
        up = implements.get(n, [])
        if kinds.get(n) not in (NodeKind.capability, NodeKind.workflow):
            up = parents.get(n, []) + up
        for nxt in up:
            if nxt not in paths:
                paths[nxt] = [*paths[n], nxt]
                q.append(nxt)
    return paths


def _match(patterns: list[str], keys: set[str]) -> str | None:
    for p in patterns:
        for k in sorted(keys):
            if fnmatch.fnmatchcase(k, p):
                return k
    return None


# ---------------------------------------------------------------------------- main


def _keys_overlapping(facts: list[Fact], path: str, h: Hunk) -> set[str]:
    return {
        f.key
        for f in facts
        if f.locator.path == path
        and f.kind not in ("module", "call_edge")
        and (
            _overlaps(f.locator.line_start, f.locator.line_end, h.new_start, h.new_lines)
            or _overlaps(f.locator.line_start, f.locator.line_end, h.old_start, h.old_lines)
        )
    }


def _changed_lines_match(
    cf: ChangedFile, base_root: Path, head_root: Path, pattern: re.Pattern[str]
) -> bool:
    if cf.status != "modified":
        return True
    a = (base_root / cf.path).read_text(encoding="utf-8", errors="replace").splitlines()
    b = (head_root / cf.path).read_text(encoding="utf-8", errors="replace").splitlines()
    for h in cf.hunks:
        lines = (
            a[h.old_start - 1 : h.old_start - 1 + h.old_lines]
            + b[h.new_start - 1 : h.new_start - 1 + h.new_lines]
        )
        if any(pattern.search(x) for x in lines):
            return True
    return False


@dataclass
class ImpactResult:
    impact: PRImpact
    categories: set[str]
    affected_paths: dict[str, list[str]]


def analyze_impact(
    base: TreeState,
    head: TreeState,
    suite: list[SuiteItem],
    *,
    pr_number: int = 0,
    base_sha: str = "base",
    head_sha: str = "head",
) -> ImpactResult:
    changed = diff_trees(base, head)
    by_path = {c.path: c for c in changed}
    head_nodes = {n.key: n for n in head.graph.nodes}
    base_nodes = {n.key: n for n in base.graph.nodes}

    touched: dict[str, TouchedNode] = {}

    def touch(
        key: str, via: TouchVia, attr_changes: dict[str, tuple[Any, Any]] | None = None
    ) -> None:
        if key not in head_nodes and key not in base_nodes:
            return
        t = touched.setdefault(key, TouchedNode(node_key=key, via=via))
        if attr_changes:
            t.attr_changes.update(attr_changes)

    def via_for(f: Fact) -> TouchVia:
        if f.kind in ("config_key", "serving_config"):
            return TouchVia.config_key
        if f.kind in ("prompt", "system_message"):
            return TouchVia.prompt_segment
        if f.kind == "dependency":
            return TouchVia.dependency
        return (
            TouchVia.symbol
            if f.kind in ("function", "llm_call", "side_effect_function", "retriever")
            else TouchVia.file
        )

    for side, facts in (("head", head.facts), ("base", base.facts)):
        for key, fs in _touched_by_hunks(facts, by_path, side).items():
            touch(key, via_for(fs[0]))
            # a call-site / tool / retriever fact keyed differently from its function component
            for f in fs:
                fk = f.data.get("function_key") or f.data.get("component_key")
                if isinstance(fk, str):
                    touch(fk, TouchVia.symbol)

    # semantic attribute changes (positions excluded) and added/removed nodes
    for key in set(head_nodes) | set(base_nodes):
        b, h = base_nodes.get(key), head_nodes.get(key)
        if b is None or h is None:
            touch(key, TouchVia.symbol, {"exists": (b is not None, h is not None)})
            continue
        diffs = {
            k: (b.attrs.get(k), h.attrs.get(k))
            for k in set(b.attrs) | set(h.attrs)
            if k not in POSITIONAL_ATTRS and b.attrs.get(k) != h.attrs.get(k)
        }
        if diffs:
            touch(
                key,
                TouchVia.config_key
                if h.kind in (NodeKind.config_key, NodeKind.serving_config)
                else TouchVia.symbol,
                diffs,
            )

    categories: set[str] = set()
    for key, t in touched.items():
        node = head_nodes.get(key) or base_nodes.get(key)
        categories |= categorize(key, node.kind if node else None, t.attr_changes)

    # unmapped application-code changes -> conservative full-suite fallback
    fallback_reasons: list[str] = []
    all_facts = head.facts + base.facts
    for cf in changed:
        if DEPENDENCY_FILES.search(cf.path):
            categories.add("dependency")
            if _changed_lines_match(cf, base.root, head.root, LLM_SDK_NAMES):
                categories.add("llm_sdk")
            continue
        if not cf.path.endswith(".py") or cf.path.startswith(NON_APP_PREFIXES):
            if cf.path.startswith(("tests/", "test/")):
                categories.add("tests")
            elif cf.path.endswith((".md", ".rst", ".txt")) or cf.path.startswith("docs/"):
                categories.add("docs")
            continue
        head_lines = (
            (head.root / cf.path).read_text(encoding="utf-8", errors="replace").splitlines()
            if (head.root / cf.path).exists()
            else []
        )
        for h in cf.hunks:
            new = head_lines[h.new_start - 1 : h.new_start - 1 + h.new_lines]
            if all(IGNORABLE_LINE.match(x) for x in new) and h.new_lines > 0:
                categories.add("imports")  # import/comment-only hunk: no behavior by itself
                continue
            mapped = any(
                f.locator.path == cf.path
                and (
                    _overlaps(f.locator.line_start, f.locator.line_end, h.new_start, h.new_lines)
                    or _overlaps(f.locator.line_start, f.locator.line_end, h.old_start, h.old_lines)
                )
                for f in all_facts
                if f.kind not in ("module", "call_edge")
            )
            if not mapped:
                fallback_reasons.append(
                    f"{cf.path}:{h.new_start} changes code that maps to no graph node"
                )
            elif not any(
                k in head_nodes or k in base_nodes for k in _keys_overlapping(all_facts, cf.path, h)
            ):
                categories.add("code_off_llm_path")

    graph = head.graph if head.graph.nodes else base.graph
    merged = Graph(
        nodes=graph.nodes + [n for k, n in base_nodes.items() if k not in head_nodes],
        edges=graph.edges + base.graph.edges,
    )
    paths = _ancestors(merged, set(touched))
    affected = set(paths)

    selected: list[Selection] = []
    skipped: list[Selection] = []
    fell_back = bool(fallback_reasons)
    for item in suite:
        if fell_back:
            selected.append(
                Selection(
                    key=item.key,
                    kind=item.kind,
                    reason="full suite: " + "; ".join(fallback_reasons[:3]),
                )
            )
            continue
        if item.always:
            selected.append(
                Selection(key=item.key, kind=item.kind, reason="always runs (cheap safety check)")
            )
            continue
        if item.kind == "unit" and item.key.split(":", 1)[1] in by_path:
            selected.append(
                Selection(key=item.key, kind=item.kind, reason="the test file itself changed")
            )
            continue
        if "dependency" in categories and "dependency" in item.triggers:
            # a dependency manifest change can affect any code path, regardless of graph binding
            selected.append(
                Selection(key=item.key, kind=item.kind, reason="a dependency manifest changed")
            )
            continue
        if "llm_sdk" in categories and "llm_sdk" in item.triggers:
            selected.append(
                Selection(
                    key=item.key, kind=item.kind, reason="an LLM SDK / serving dependency changed"
                )
            )
            continue
        hit = _match(item.binds, affected)
        trig = "*" in item.triggers or bool(item.triggers & categories)
        if hit and trig:
            cats = (
                sorted(item.triggers & categories)
                if "*" not in item.triggers
                else sorted(categories)
            )
            selected.append(
                Selection(
                    key=item.key,
                    kind=item.kind,
                    reason=f"{', '.join(cats)} change reaches {hit}",
                    path=paths[hit],
                )
            )
        elif hit:
            skipped.append(
                Selection(
                    key=item.key,
                    kind=item.kind,
                    reason=f"exercises {hit}, but the change ({', '.join(sorted(categories)) or 'none'}) is not one it detects",
                )
            )
        else:
            skipped.append(
                Selection(
                    key=item.key, kind=item.kind, reason="exercises nothing this change touches"
                )
            )

    impact = PRImpact(
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        changed=changed,
        touched=sorted(touched.values(), key=lambda t: t.node_key),
        affected_keys=sorted(affected),
        selected=selected,
        skipped=skipped,
        full_suite_size=len(suite),
        fell_back_to_full=fell_back,
    )
    return ImpactResult(impact=impact, categories=categories, affected_paths=paths)
