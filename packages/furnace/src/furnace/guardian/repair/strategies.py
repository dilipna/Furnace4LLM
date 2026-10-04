"""Deterministic repair strategies.

`move_dynamic_to_suffix` repairs a prefix-unstable system message: it keeps every
runtime value the author added (so the PR's intent, e.g. "log the request id in the
prompt", survives) but moves those values *after* the static text, so all requests
share the static prefix again. The edit replaces exactly the content expression's
character span, leaving the rest of the file byte-identical.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


class StrategyError(Exception):
    pass


@dataclass
class Edit:
    path: str
    before: str
    after: str
    explanation: str


def _flatten_add(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten_add(node.left) + _flatten_add(node.right)
    return [node]


def _is_static(node: ast.expr, static_names: set[str]) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.Name) and node.id in static_names:
        return True
    return isinstance(node, ast.JoinedStr) and all(isinstance(v, ast.Constant) for v in node.values)


def _span(src: str, node: ast.expr) -> tuple[int, int]:
    lines = src.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def off(lineno: int, col: int) -> int:
        # ast column offsets are in UTF-8 bytes
        line = lines[lineno - 1]
        return starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", errors="ignore"))

    return off(node.lineno, node.col_offset), off(
        node.end_lineno or node.lineno, node.end_col_offset or 0
    )


def move_dynamic_to_suffix(path: str, source: str, function: str) -> Edit:
    """Rewrite the system-message content inside `function` so static text comes first."""
    tree = ast.parse(source)
    static_names = {
        t.id
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    fn = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == function.split(".")[-1]
        ),
        None,
    )
    if fn is None:
        raise StrategyError(f"function {function} not found in {path}")
    content = None
    for d in ast.walk(fn):
        if isinstance(d, ast.Dict):
            pairs = {
                k.value: v
                for k, v in zip(d.keys, d.values, strict=True)
                if isinstance(k, ast.Constant)
            }
            role = pairs.get("role")
            if isinstance(role, ast.Constant) and role.value == "system" and "content" in pairs:
                content = pairs["content"]
                break
    if content is None:
        raise StrategyError(f"no system message in {function}")

    parts = _flatten_add(content)
    if len(parts) == 1 and isinstance(content, ast.JoinedStr):
        # f"{dynamic}...{STATIC}..." -> static pieces first, then the dynamic remainder
        raise StrategyError("single f-string system message: not supported by this strategy yet")
    statics = [p for p in parts if _is_static(p, static_names)]
    dynamics = [p for p in parts if not _is_static(p, static_names)]
    if not statics or not dynamics:
        raise StrategyError("system message has no static/dynamic split to reorder")
    if parts[: len(statics)] == statics:
        raise StrategyError("static text already comes first; prefix is stable")

    seg = lambda n: ast.get_source_segment(source, n) or ""  # noqa: E731
    new_expr = " + ".join([*(seg(p) for p in statics), '"\\n"', *(seg(p) for p in dynamics)])
    start, end = _span(source, content)
    after = source[:start] + new_expr + source[end:]
    ast.parse(after)  # the edit must still be valid Python
    moved = ", ".join(seg(p) for p in dynamics)
    return Edit(
        path=path,
        before=source,
        after=after,
        explanation=(
            f"Moved the per-request value(s) {moved} from the start of the system message to its end. "
            "They are still sent to the model, but every request now begins with the same static text, "
            "so the serving engine's prefix cache can reuse its prefill."
        ),
    )
