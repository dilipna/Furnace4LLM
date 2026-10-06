"""Evaluation harness generation by handler slicing.

To evaluate or benchmark an application we need the exact messages it would send
to the model for a given input, without running the web server or the model.
For a route handler like

    @app.post("/chat")
    def chat(req: ChatRequest):
        cfg = rag_config()
        chunks = retrieve(req.question, top_k=cfg["retrieval"]["top_k"])
        messages = build_messages(req.question, chunks, ...)
        return StreamingResponse(stream_answer(messages, ...))

we keep the statements up to (and including) the assignment that calls the
component owning the system message, replace the request parameter with a
stand-in object carrying the question, and import exactly the module-level names
those statements use. The result is `furnace_harness.py` with `render(question)`.

If the handler does not have this shape, generation fails loudly; it never
guesses.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path

from furnace.code_intel.python_ast import dotted, module_name
from furnace.contracts.graph import NodeKind
from furnace.reconstruction.build import Reconstruction

HARNESS_FILE = "furnace_harness.py"


class HarnessError(Exception):
    pass


@dataclass
class Harness:
    source: str
    handler: str  # "app/main.py::chat"
    request_param: str
    question_field: str
    builder: str  # qualname of the system-message builder
    has_answer: bool = False  # answer(question) available (full answer path)


def _handler_for_llm_workflow(rec: Reconstruction) -> tuple[str, str]:
    """(path, qualname) of the route handler of the first workflow that builds a system message."""
    builders = {f.data["component_key"] for f in rec.facts.of("system_message")}
    if not builders:
        raise HarnessError("no system-message construction found in the code")
    callees: dict[str, set[str]] = {}
    for e in rec.facts.of("call_edge"):
        callees.setdefault(e.key, set()).add(e.data["callee_key"])

    def reaches(start: str, target: set[str]) -> bool:
        seen, todo = set(), [start]
        while todo:
            n = todo.pop()
            if n in target:
                return True
            if n not in seen:
                seen.add(n)
                todo.extend(callees.get(n, ()))
        return False

    for r in sorted(rec.facts.of("route"), key=lambda f: f.data["path"]):
        handler = r.data["handler_key"]
        if reaches(handler, builders):
            path, qual = handler.removeprefix(f"{NodeKind.component.value}:").split("::", 1)
            return path, qual
    raise HarnessError("no route handler reaches the system-message builder")


def _find_function(tree: ast.Module, qualname: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    node: ast.AST = tree
    for part in qualname.split("."):
        found = None
        for child in ast.iter_child_nodes(node):
            if (
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and child.name == part
            ):
                found = child
                break
        if found is None:
            raise HarnessError(f"function {qualname} not found")
        node = found
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise HarnessError(f"{qualname} is not a function")
    return node


def generate_harness(rec: Reconstruction) -> Harness:
    path, qual = _handler_for_llm_workflow(rec)
    root = rec.inventory.root
    src = (root / path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = _find_function(tree, qual)
    builder_keys = [f.data["component_key"] for f in rec.facts.of("system_message")]
    builder_names = {k.split("::", 1)[1].split(".")[-1] for k in builder_keys}

    # request parameter: the first parameter whose attributes the handler reads
    params = [a.arg for a in fn.args.args]
    attr_reads: dict[str, list[str]] = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in params:
            attr_reads.setdefault(n.value.id, []).append(n.attr)
    if not attr_reads:
        raise HarnessError(f"{path}::{qual} reads no request fields")
    req_param = next(p for p in params if p in attr_reads)
    question_field = attr_reads[req_param][0]

    # slice: statements up to the assignment that calls the builder
    sliced: list[ast.stmt] = []
    target_var = None
    for stmt in fn.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring
        sliced.append(stmt)
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            name = (dotted(stmt.value.func) or "").split(".")[-1]
            if (
                name in builder_names
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
            ):
                target_var = stmt.targets[0].id
                break
        if isinstance(stmt, (ast.Return, ast.If, ast.For, ast.While, ast.Try, ast.With)):
            raise HarnessError(
                f"{path}::{qual}: control flow before the messages are built; cannot slice safely"
            )
    if target_var is None:
        raise HarnessError(f"{path}::{qual} does not assign the result of {sorted(builder_names)}")

    # answer(): continue past the messages to the call that consumes them (the model call
    # plus any post-processing the app applies), keeping only plain assignments in between.
    answer_pre: list[ast.stmt] = []
    producer: ast.Call | None = None
    for stmt in fn.body[fn.body.index(sliced[-1]) + 1 :]:
        consumer = _consumer_call(stmt, target_var)
        if consumer is not None:
            producer = consumer
            break
        if isinstance(stmt, ast.Assign):
            answer_pre.append(stmt)
            continue
        break  # control flow or anything else: no safe answer path

    # names used by the slice that come from the handler's module scope
    module_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_names |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_names.add(node.name)
        elif isinstance(node, ast.Assign):
            module_names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    assigned = {
        t.id
        for s in sliced
        if isinstance(s, ast.Assign)
        for t in s.targets
        if isinstance(t, ast.Name)
    }
    answer_nodes: list[ast.AST] = [*answer_pre, producer] if producer is not None else []
    assigned |= {
        t.id
        for s in answer_pre
        if isinstance(s, ast.Assign)
        for t in s.targets
        if isinstance(t, ast.Name)
    }
    used = sorted(
        {n.id for s in [*sliced, *answer_nodes] for n in ast.walk(s) if isinstance(n, ast.Name)}
        & module_names - assigned - {req_param}
    )

    seg = lambda n: textwrap.dedent(ast.get_source_segment(src, n) or "")  # noqa: E731
    body = "\n".join(seg(s) for s in sliced)
    mod = module_name(path)
    imports = f"from {mod} import {', '.join(used)}\n" if used else ""
    source = (
        f'"""Generated by Furnace Forge from {path}::{qual}.\n\n'
        f"render(question): the exact chat messages the handler sends to the model, without\n"
        f"starting the server or calling the model.\n"
        + (
            "answer(question): the handler's full answer path (model call and any output\n"
            "post-processing), as text. Needs the app's model endpoint.\n"
            if producer is not None
            else ""
        )
        + f'Regenerate this file if that handler changes."""\n\n'
        f"from types import SimpleNamespace\n\n"
        f"{imports}\n\n"
        f"def render(question: str) -> list[dict]:\n"
        f"    {req_param} = SimpleNamespace({question_field}=question)\n"
        + textwrap.indent(body, "    ")
        + f"\n    return {target_var}\n"
    )
    if producer is not None:
        pre = "\n".join(seg(s) for s in answer_pre)
        source += (
            "\n\ndef answer(question: str) -> str:\n"
            f"    {req_param} = SimpleNamespace({question_field}=question)\n"
            + textwrap.indent(body, "    ")
            + ("\n" + textwrap.indent(pre, "    ") if pre else "")
            + f"\n    out = {seg(producer)}\n"
            '    return out if isinstance(out, str) else "".join(out)\n'
        )
    compile(source, HARNESS_FILE, "exec")  # must at least be valid Python
    return Harness(
        source=source,
        handler=f"{path}::{qual}",
        request_param=req_param,
        question_field=question_field,
        builder=sorted(builder_names)[0],
        has_answer=producer is not None,
    )


def _consumer_call(stmt: ast.stmt, var: str) -> ast.Call | None:
    """Innermost call in `stmt` that receives `var` as an argument (positional or keyword)."""
    best: ast.Call | None = None
    for n in ast.walk(stmt):
        if isinstance(n, ast.Call):
            args = [*n.args, *(k.value for k in n.keywords)]
            if any(isinstance(a, ast.Name) and a.id == var for a in args):
                best = n  # ast.walk is breadth-first: later matches are nested deeper
    return best


def write_harness(rec: Reconstruction, root: Path | None = None) -> Harness:
    h = generate_harness(rec)
    (root or rec.inventory.root).joinpath(HARNESS_FILE).write_text(h.source, encoding="utf-8")
    return h
