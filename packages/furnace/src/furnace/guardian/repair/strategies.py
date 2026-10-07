"""Deterministic repair strategies.

`move_dynamic_to_suffix` repairs a prefix-unstable system message: it keeps every
runtime value the author added (so the PR's intent, e.g. "log the request id in the
prompt", survives) but moves those values to the end of the last user message when the
messages are built as one list literal (so the system prompt and the retrieved context
both stay cacheable), otherwise to the end of the system message. The edit replaces
exactly the content expressions' character spans, leaving the rest of the file
byte-identical.
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

    def fields(d: ast.Dict) -> dict[object, ast.expr]:
        return {
            k.value: v for k, v in zip(d.keys, d.values, strict=True) if isinstance(k, ast.Constant)
        }

    def role_of(d: ast.Dict) -> object:
        r = fields(d).get("role")
        return r.value if isinstance(r, ast.Constant) else None

    content = None
    last_content = None  # content of the last user message after the system one, if any
    for lst in ast.walk(fn):
        if not isinstance(lst, ast.List):
            continue
        dicts = [e for e in lst.elts if isinstance(e, ast.Dict)]
        sys_idx = next(
            (i for i, d in enumerate(dicts) if role_of(d) == "system" and "content" in fields(d)),
            None,
        )
        if sys_idx is None:
            continue
        content = fields(dicts[sys_idx])["content"]
        later = [d for d in dicts[sys_idx + 1 :] if "content" in fields(d)]
        if later and role_of(later[-1]) == "user":
            last_content = fields(later[-1])["content"]
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
    moved = ", ".join(seg(p) for p in dynamics)
    if last_content is not None:
        # Preferred: per-request values go to the very end of the last user message, so the
        # system prompt AND everything after it (e.g. the retrieved context) stay reusable.
        edits = [
            (_span(source, content), " + ".join(seg(p) for p in statics)),
            (
                _span(source, last_content),
                " + ".join([f"({seg(last_content)})", '"\\n\\n"', *(seg(p) for p in dynamics)]),
            ),
        ]
        where = "to the end of the last user message"
        why = (
            "every request now begins with the same static system prompt and nothing per-request "
            "precedes the retrieved context, so the prefix cache can reuse both"
        )
    else:
        edits = [
            (
                _span(source, content),
                " + ".join([*(seg(p) for p in statics), '"\\n"', *(seg(p) for p in dynamics)]),
            )
        ]
        where = "to the end of the system message"
        why = "every request now begins with the same static text, so the prefix cache can reuse it"
    after = source
    for (start, end), text in sorted(edits, key=lambda e: e[0][0], reverse=True):
        after = after[:start] + text + after[end:]
    ast.parse(after)  # the edit must still be valid Python
    return Edit(
        path=path,
        before=source,
        after=after,
        explanation=(
            f"Moved the per-request value(s) {moved} from the start of the system message {where}. "
            f"They are still sent to the model, but {why}."
        ),
    )
