"""Deterministic repair strategies, tried in order (STRATEGIES).

`move_dynamic_to_suffix` repairs a prefix-unstable system message: it keeps every
runtime value the author added (so the PR's intent, e.g. "log the request id in the
prompt", survives) but moves those values to the end of the last user message when the
messages are built as one list literal (so the system prompt and the retrieved context
both stay cacheable), otherwise to the end of the system message. The edit replaces
exactly the content expressions' character spans, leaving the rest of the file
byte-identical.

`move_dynamic_to_log` takes the per-request values out of the prompt and logs them with
the standard `logging` module right before the messages are built: the debugging intent
survives in the logs and the prompt prefix is exactly the base revision's again. The
model no longer sees those values, which the repair PR states.
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


@dataclass
class _SystemMessage:
    fn: ast.FunctionDef | ast.AsyncFunctionDef
    content: ast.expr
    last_content: ast.expr | None
    statics: list[ast.expr]
    dynamics: list[ast.expr]


def _system_message(source: str, function: str) -> _SystemMessage:
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
        raise StrategyError(f"function {function} not found")

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
    return _SystemMessage(fn, content, last_content, statics, dynamics)


def _apply(source: str, edits: list[tuple[tuple[int, int], str]]) -> str:
    after = source
    for (start, end), text in sorted(edits, key=lambda e: e[0][0], reverse=True):
        after = after[:start] + text + after[end:]
    ast.parse(after)  # the edit must still be valid Python
    return after


def move_dynamic_to_suffix(path: str, source: str, function: str) -> Edit:
    """Rewrite the system-message content inside `function` so static text comes first."""
    m = _system_message(source, function)
    content, last_content, statics, dynamics = m.content, m.last_content, m.statics, m.dynamics
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
    return Edit(
        path=path,
        before=source,
        after=_apply(source, edits),
        explanation=(
            f"Moved the per-request value(s) {moved} from the start of the system message {where}. "
            f"They are still sent to the model, but {why}."
        ),
    )


def _line_start(source: str, lineno: int) -> int:
    return sum(len(line) for line in source.splitlines(keepends=True)[: lineno - 1])


def move_dynamic_to_log(path: str, source: str, function: str) -> Edit:
    """Drop the per-request values from the system message and log them instead."""
    m = _system_message(source, function)
    seg = lambda n: ast.get_source_segment(source, n) or ""  # noqa: E731
    stmt = next(
        st for st in m.fn.body if st.lineno <= m.content.lineno <= (st.end_lineno or st.lineno)
    )
    indent = " " * stmt.col_offset
    fmt = " ".join(["%s"] * len(m.dynamics))
    args = ", ".join(seg(p) for p in m.dynamics)
    log_line = (
        f"{indent}logging.getLogger(__name__).info(\n"
        f'{indent}    "per-request values (logged, not sent in the prompt): {fmt}", {args}\n'
        f"{indent})\n"
    )
    edits = [
        (_span(source, m.content), " + ".join(seg(p) for p in m.statics)),
        ((_line_start(source, stmt.lineno),) * 2, log_line),
    ]
    tree = ast.parse(source)
    has_logging = any(
        isinstance(n, ast.Import) and any(a.name == "logging" for a in n.names) for n in tree.body
    )
    if not has_logging:
        imports = [
            n
            for n in tree.body
            if isinstance(n, (ast.Import, ast.ImportFrom))
            and not (isinstance(n, ast.ImportFrom) and n.module == "__future__")
        ]
        if imports:
            at = _line_start(source, imports[0].lineno)
        else:  # after a module docstring / __future__ imports, else at the top
            lead = [
                n
                for n in tree.body
                if (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
                or (isinstance(n, ast.ImportFrom) and n.module == "__future__")
            ]
            at = _line_start(source, (lead[-1].end_lineno or lead[-1].lineno) + 1) if lead else 0
        edits.append(((at, at), "import logging\n"))
    moved = ", ".join(seg(p) for p in m.dynamics)
    return Edit(
        path=path,
        before=source,
        after=_apply(source, edits),
        explanation=(
            f"Removed the per-request value(s) {moved} from the system message and log them with "
            "the standard logging module just before the messages are built. The debugging "
            "information is kept in the application log, and every request again starts with "
            "exactly the base revision's prompt, so the prefix cache reuses all of it. Trade-off: "
            "the model no longer sees these values; if it needs them, the suffix variant keeps "
            "them in the prompt at the measured latency cost."
        ),
    )


# Tried in order; the first candidate that passes the tests and the perf budget is proposed.
STRATEGIES = {
    "rule:prefix_stability.move_dynamic_to_suffix": move_dynamic_to_suffix,
    "rule:prefix_stability.move_dynamic_to_log": move_dynamic_to_log,
}
