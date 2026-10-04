"""Deterministic Python extraction with the standard-library ``ast`` module.

Produces Facts for: module constants, LLM clients and call sites (with resolved
model / base_url / stream / timeout), routes, prompts (static vs dynamic
segments, prefix stability), retrievers, side-effecting functions (tools) with
approval-gate detection, reliability mechanisms, and the intra-repo call graph.

Everything here is *observed* in source. Where a conclusion requires a
heuristic (e.g. "this guard is an approval gate") the fact says so in its data
(``heuristic: True``) and reconstruction assigns lower confidence.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from furnace.code_intel.facts import Fact
from furnace.code_intel.inventory import Inventory, RepoFile
from furnace.contracts.common import Locator, Observation
from furnace.contracts.graph import NodeKind, node_key
from furnace.security.redact import redact

EXTRACTOR = "py_ast@1"

LLM_CLIENT_CLASSES = {
    "OpenAI": "openai",
    "AsyncOpenAI": "openai",
    "AzureOpenAI": "azure_openai",
    "AsyncAzureOpenAI": "azure_openai",
    "Anthropic": "anthropic",
    "AsyncAnthropic": "anthropic",
    "Groq": "groq",
    "AsyncGroq": "groq",
    "ChatOpenAI": "openai",
    "ChatAnthropic": "anthropic",
    "ChatOllama": "ollama",
    "Client": "ollama",  # ollama.Client; only when imported from ollama (checked)
}

# dotted-suffix -> API name
LLM_CALL_SUFFIXES = {
    "chat.completions.create": "openai.chat.completions.create",
    "chat.completions.parse": "openai.chat.completions.parse",
    "beta.chat.completions.parse": "openai.chat.completions.parse",
    "chat.completions.stream": "openai.chat.completions.stream",
    "responses.create": "openai.responses.create",
    "responses.stream": "openai.responses.stream",
    "completions.create": "openai.completions.create",
    "messages.create": "anthropic.messages.create",
    "messages.stream": "anthropic.messages.stream",
}
LLM_FUNCS = {
    ("litellm", "completion"): "litellm.completion",
    ("litellm", "acompletion"): "litellm.acompletion",
    ("ollama", "chat"): "ollama.chat",
    ("ollama", "generate"): "ollama.generate",
}
LANGCHAIN_INVOKE = {"invoke", "ainvoke", "stream", "astream"}

ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "route", "api_route", "websocket"}
WEB_APP_CLASSES = {"FastAPI", "APIRouter", "Flask", "Blueprint"}

# Query-time retrieval calls (index construction such as BM25Okapi(...) is not a retriever).
RETRIEVAL_CALLS = {
    "get_scores": "bm25",
    "get_top_n": "bm25",
    "similarity_search": "vector",
    "similarity_search_with_score": "vector",
    "similarity_search_by_vector": "vector",
    "max_marginal_relevance_search": "vector",
    "get_relevant_documents": "vector",
    "query_points": "qdrant",
}
# Generic method names that count only when the module imports a retrieval library.
GENERIC_RETRIEVAL_CALLS = {"query", "search"}
RETRIEVAL_MODULES = {
    "rank_bm25": "bm25",
    "chromadb": "chroma",
    "qdrant_client": "qdrant",
    "pinecone": "pinecone",
    "faiss": "faiss",
    "pgvector": "pgvector",
    "weaviate": "weaviate",
    "lancedb": "lancedb",
}

HTTP_MODULES = {"httpx", "requests", "aiohttp", "urllib3"}
HTTP_WRITE_METHODS = {"post", "put", "patch", "delete"}
APPROVAL_PARAMS = re.compile(
    r"^(approved?|confirm(ed)?|user_confirmed|human_approved|is_approved|allow)$"
)
PROMPT_NAME = re.compile(r"(?i)prompt|system|instruction|template|persona|preamble")
LOGGING_NAME = re.compile(r"(?i)(^|_)(log|logger|logging|trace|tracing|telemetry|metric|audit)")


# ---------------------------------------------------------------------------- helpers


def dotted(node: ast.AST) -> str | None:
    """`a.b.c` for Name/Attribute chains (calls in the chain are rendered as `()`)."""
    parts: list[str] = []
    while True:
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        elif isinstance(node, ast.Call):
            parts.append("()")
            node = node.func
        else:
            return None


def module_name(path: str) -> str:
    p = path[:-3] if path.endswith(".py") else path
    parts = [x for x in p.split("/") if x]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


@dataclass
class Resolved:
    kind: str  # literal | env | param | unknown | dynamic
    value: Any = None
    env: str | None = None
    default: Any = None
    note: str = ""

    def display(self) -> str:
        if self.kind == "literal":
            return repr(self.value)
        if self.kind == "env":
            return f"env:{self.env}" + (
                f" (default {self.default!r})" if self.default is not None else ""
            )
        return f"{self.kind}:{self.note}" if self.note else self.kind

    def effective(self) -> Any:
        """Best static value: literal, or env default."""
        if self.kind == "literal":
            return self.value
        if self.kind == "env":
            return self.default
        return None


@dataclass
class FuncInfo:
    qualname: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    params: list[str]
    calls: list[tuple[str, int]] = field(default_factory=list)  # (dotted callee, line)
    names: set[str] = field(default_factory=set)


@dataclass
class ModInfo:
    file: RepoFile
    name: str
    tree: ast.Module
    lines: list[str]
    consts: dict[str, ast.expr] = field(default_factory=dict)
    imports: dict[str, tuple[str, str | None]] = field(
        default_factory=dict
    )  # local -> (module, name)
    funcs: dict[str, FuncInfo] = field(default_factory=dict)
    clients: dict[str, ast.Call] = field(default_factory=dict)  # var -> constructor call
    web_apps: set[str] = field(default_factory=set)


class PythonExtractor:
    def __init__(self, inventory: Inventory) -> None:
        self.inv = inventory
        self.mods: dict[str, ModInfo] = {}
        self.facts: list[Fact] = []

    # ------------------------------------------------------------------ parsing

    def run(self) -> list[Fact]:
        for f in self.inv.by_lang("python"):
            try:
                src = self.inv.read(f)
                tree = ast.parse(src, filename=f.path)
            except (SyntaxError, ValueError):
                continue
            mod = ModInfo(file=f, name=module_name(f.path), tree=tree, lines=src.splitlines())
            self._index_module(mod)
            self.mods[mod.name] = mod
        for mod in self.mods.values():
            self._extract_module(mod)
        return self.facts

    def _index_module(self, mod: ModInfo) -> None:
        pkg = mod.name.rsplit(".", 1)[0] if "." in mod.name else ""
        for node in mod.tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    mod.imports[a.asname or a.name.split(".")[0]] = (
                        a.name if a.asname else a.name.split(".")[0],
                        None,
                    )
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    up = pkg.split(".") if pkg else []
                    up = up[: len(up) - (node.level - 1)] if node.level > 1 else up
                    base = ".".join([*up, base] if base else up)
                for a in node.names:
                    mod.imports[a.asname or a.name] = (base, a.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                if value is None:
                    continue
                for t in targets:
                    if isinstance(t, ast.Name):
                        mod.consts[t.id] = value
                        if isinstance(value, ast.Call):
                            cls = dotted(value.func) or ""
                            short = cls.split(".")[-1]
                            if short in LLM_CLIENT_CLASSES and self._is_llm_client(mod, cls):
                                mod.clients[t.id] = value
                            if short in WEB_APP_CLASSES:
                                mod.web_apps.add(t.id)
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = self._qualname(mod.tree, node)
                info = FuncInfo(
                    qualname=qual,
                    node=node,
                    params=[a.arg for a in node.args.args + node.args.kwonlyargs],
                )
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        d = dotted(sub.func)
                        if d:
                            info.calls.append((d, sub.lineno))
                    elif isinstance(sub, ast.Name):
                        info.names.add(sub.id)
                mod.funcs[qual] = info

    def _is_llm_client(self, mod: ModInfo, cls: str) -> bool:
        short = cls.split(".")[-1]
        if short != "Client":
            return True
        root = cls.split(".")[0]
        origin = mod.imports.get(root) or mod.imports.get(short)
        return bool(origin and origin[0].startswith("ollama"))

    @staticmethod
    def _qualname(tree: ast.Module, target: ast.AST) -> str:
        path: list[str] = []

        def visit(node: ast.AST, stack: list[str]) -> bool:
            for child in ast.iter_child_nodes(node):
                if child is target:
                    path.extend([*stack, child.name])  # type: ignore[attr-defined]
                    return True
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if visit(child, [*stack, child.name]):
                        return True
                elif visit(child, stack):
                    return True
            return False

        visit(tree, [])
        return ".".join(path)

    # ------------------------------------------------------------------ resolution

    def _find_module(self, name: str) -> ModInfo | None:
        if name in self.mods:
            return self.mods[name]
        for k, m in self.mods.items():
            if k.endswith("." + name) or name.endswith("." + k):
                return m
        return None

    def resolve(
        self, mod: ModInfo, expr: ast.expr | None, depth: int = 0, func: FuncInfo | None = None
    ) -> Resolved:
        if expr is None:
            return Resolved("unknown")
        if depth > 4:
            return Resolved("unknown", note="depth")
        if isinstance(expr, ast.Constant):
            return Resolved("literal", expr.value)
        if isinstance(expr, ast.JoinedStr):
            return Resolved("dynamic", note="f-string")
        if isinstance(expr, ast.Call):
            d = dotted(expr.func) or ""
            if d in ("os.getenv", "os.environ.get", "getenv", "environ.get") and expr.args:
                env = self.resolve(mod, expr.args[0], depth + 1)
                default = self.resolve(mod, expr.args[1], depth + 1) if len(expr.args) > 1 else None
                return Resolved(
                    "env", env=str(env.value), default=default.effective() if default else None
                )
        if isinstance(expr, ast.Subscript) and dotted(expr.value) in ("os.environ", "environ"):
            key = self.resolve(mod, expr.slice, depth + 1)  # type: ignore[arg-type]
            return Resolved("env", env=str(key.value))
        if isinstance(expr, ast.Name):
            if func and expr.id in func.params:
                return Resolved("param", note=expr.id)
            if expr.id in mod.consts:
                return self.resolve(mod, mod.consts[expr.id], depth + 1)
            if expr.id in mod.imports:
                origin_mod, origin_name = mod.imports[expr.id]
                target = self._find_module(origin_mod)
                if target and origin_name and origin_name in target.consts:
                    return self.resolve(target, target.consts[origin_name], depth + 1)
            return Resolved("unknown", note=expr.id)
        if isinstance(expr, ast.Attribute):
            return Resolved("unknown", note=dotted(expr) or "attr")
        return Resolved("unknown")

    def _loc(self, mod: ModInfo, node: ast.AST, symbol: str | None = None) -> Locator:
        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", start)
        return Locator(path=mod.file.path, line_start=start, line_end=end, symbol=symbol)

    def _excerpt(self, mod: ModInfo, node: ast.AST, max_lines: int = 6) -> str:
        start = getattr(node, "lineno", 1) - 1
        end = min(getattr(node, "end_lineno", start + 1), start + max_lines)
        return redact("\n".join(mod.lines[start:end]))[:480]

    def _emit(
        self,
        kind: str,
        key: str,
        data: dict[str, Any],
        mod: ModInfo,
        node: ast.AST,
        *,
        symbol: str | None = None,
        observation: Observation = Observation.direct_observation,
    ) -> None:
        self.facts.append(
            Fact(
                kind=kind,
                key=key,
                data=data,
                locator=self._loc(mod, node, symbol),
                excerpt=self._excerpt(mod, node),
                extractor=f"{EXTRACTOR}.{kind}",
                observation=observation,
            )
        )

    # ------------------------------------------------------------------ extraction

    def _func_key(self, mod: ModInfo, qual: str) -> str:
        return node_key(NodeKind.component, mod.file.path, qual)

    def _extract_module(self, mod: ModInfo) -> None:
        self._emit(
            "module",
            node_key(NodeKind.component, mod.file.path),
            {"module": mod.name},
            mod,
            mod.tree.body[0] if mod.tree.body else mod.tree,
        )
        for var, call in mod.clients.items():
            self._client_fact(mod, var, call)
        self._prompt_constants(mod)
        imported_modules = {origin for origin, _ in mod.imports.values()}
        for info in mod.funcs.values():
            fkey = self._func_key(mod, info.qualname)
            self._emit(
                "function",
                fkey,
                {
                    "qualname": info.qualname,
                    "params": info.params,
                    "async": isinstance(info.node, ast.AsyncFunctionDef),
                },
                mod,
                info.node,
                symbol=info.qualname,
            )
            self._routes(mod, info, fkey)
            self._llm_calls(mod, info, fkey)
            self._message_assembly(mod, info, fkey)
            self._retriever(mod, info, fkey, imported_modules)
            self._side_effects(mod, info, fkey)
            self._reliability(mod, info, fkey)
            self._call_edges(mod, info, fkey)
            self._config_access(mod, info, fkey)
            for name in info.names:
                if name in mod.consts and self._is_prompt_const(name, mod.consts[name]):
                    self._emit(
                        "uses_prompt",
                        fkey,
                        {"prompt_key": node_key(NodeKind.prompt, mod.file.path, name)},
                        mod,
                        info.node,
                        symbol=info.qualname,
                    )
                elif name in mod.imports:
                    origin_mod, origin_name = mod.imports[name]
                    target = self._find_module(origin_mod)
                    if (
                        target
                        and origin_name
                        and origin_name in target.consts
                        and self._is_prompt_const(origin_name, target.consts[origin_name])
                    ):
                        self._emit(
                            "uses_prompt",
                            fkey,
                            {
                                "prompt_key": node_key(
                                    NodeKind.prompt, target.file.path, origin_name
                                )
                            },
                            mod,
                            info.node,
                            symbol=info.qualname,
                        )
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for n in names:
                    top = n.split(".")[0]
                    if top in (
                        "opentelemetry",
                        "langfuse",
                        "langsmith",
                        "phoenix",
                        "openinference",
                        "traceloop",
                    ):
                        self._emit(
                            "tracing_import",
                            node_key(NodeKind.component, mod.file.path),
                            {"library": top},
                            mod,
                            node,
                        )
                    if top in ("tenacity", "backoff"):
                        self._emit(
                            "retry_import",
                            node_key(NodeKind.component, mod.file.path),
                            {"library": top},
                            mod,
                            node,
                        )

    # clients ---------------------------------------------------------------

    def _client_fact(self, mod: ModInfo, var: str, call: ast.Call) -> None:
        cls = (dotted(call.func) or "").split(".")[-1]
        kw = {k.arg: k.value for k in call.keywords if k.arg}
        base = self.resolve(mod, kw.get("base_url") or kw.get("api_base") or kw.get("host"))
        timeout = kw.get("timeout")
        max_retries = self.resolve(mod, kw.get("max_retries")) if "max_retries" in kw else None
        self._emit(
            "llm_client",
            node_key(NodeKind.endpoint, mod.file.path, var),
            {
                "var": var,
                "class": cls,
                "sdk": LLM_CLIENT_CLASSES.get(cls),
                "base_url": base.display(),
                "base_url_effective": base.effective(),
                "base_url_env": base.env,
                "has_timeout": timeout is not None,
                "max_retries": max_retries.effective() if max_retries else None,
            },
            mod,
            call,
            symbol=var,
        )

    # prompts ---------------------------------------------------------------

    @staticmethod
    def _is_prompt_const(name: str, value: ast.expr) -> bool:
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            return False
        text = value.value
        return len(text) >= 400 or (bool(PROMPT_NAME.search(name)) and len(text) >= 40)

    def _prompt_constants(self, mod: ModInfo) -> None:
        for name, value in mod.consts.items():
            if self._is_prompt_const(name, value):
                text = value.value  # type: ignore[attr-defined]
                self._emit(
                    "prompt",
                    node_key(NodeKind.prompt, mod.file.path, name),
                    {
                        "name": name,
                        "inline": True,
                        "static_chars": len(text),
                        "approx_tokens": round(len(text) / 4),
                        "dynamic_segments": [],
                        "static_prefix_chars": len(text),
                    },
                    mod,
                    value,
                    symbol=name,
                )

    def _segments(
        self, mod: ModInfo, expr: ast.expr, func: FuncInfo, depth: int = 0
    ) -> list[tuple[str, str]]:
        """Flatten a string expression into [("static", text) | ("dynamic", expr_src)]."""
        if depth > 6:
            return [("dynamic", "...")]
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return [("static", expr.value)]
        if isinstance(expr, ast.JoinedStr):
            out: list[tuple[str, str]] = []
            for v in expr.values:
                if isinstance(v, ast.Constant):
                    out.append(("static", str(v.value)))
                elif isinstance(v, ast.FormattedValue):
                    inner = v.value
                    if isinstance(inner, ast.Name) and inner.id not in func.params:
                        res = self.resolve(mod, inner, func=func)
                        if res.kind == "literal" and isinstance(res.value, str):
                            out.append(("static", res.value))
                            continue
                    out.append(("dynamic", ast.unparse(inner)))
            return out
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            return self._segments(mod, expr.left, func, depth + 1) + self._segments(
                mod, expr.right, func, depth + 1
            )
        if isinstance(expr, ast.Name):
            res = self.resolve(mod, expr, func=func)
            if res.kind == "literal" and isinstance(res.value, str):
                return [("static", res.value)]
        return [("dynamic", ast.unparse(expr))]

    def _message_assembly(self, mod: ModInfo, info: FuncInfo, fkey: str) -> None:
        for node in ast.walk(info.node):
            if not isinstance(node, ast.Dict):
                continue
            pairs = {
                k.value: v
                for k, v in zip(node.keys, node.values, strict=True)
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
            role = pairs.get("role")
            if not (
                isinstance(role, ast.Constant) and role.value == "system" and "content" in pairs
            ):
                continue
            segs = self._segments(mod, pairs["content"], info)
            static_total = sum(len(t) for k, t in segs if k == "static")
            prefix = 0
            dynamic: list[dict[str, Any]] = []
            offset = 0
            seen_dynamic = False
            for k, t in segs:
                if k == "static":
                    if not seen_dynamic:
                        prefix += len(t)
                    offset += len(t)
                else:
                    seen_dynamic = True
                    dynamic.append({"name": t, "char_offset": offset})
            content = pairs["content"]
            refs = [n.id for n in ast.walk(content) if isinstance(n, ast.Name)]
            self._emit(
                "system_message",
                node_key(NodeKind.prompt, mod.file.path, f"{info.qualname}#system"),
                {
                    "function": info.qualname,
                    "static_chars": static_total,
                    "static_prefix_chars": prefix,
                    "dynamic_segments": dynamic,
                    # A dynamic value before most static text defeats prefix (KV) caching.
                    "dynamic_head": bool(dynamic) and prefix < 0.5 * static_total,
                    "references": refs,
                    "component_key": fkey,
                },
                mod,
                node,
                symbol=info.qualname,
            )

    # routes ----------------------------------------------------------------

    def _routes(self, mod: ModInfo, info: FuncInfo, fkey: str) -> None:
        for dec in info.node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            method = dec.func.attr
            owner = dotted(dec.func.value) or ""
            if method not in ROUTE_METHODS:
                continue
            if owner not in mod.web_apps and not re.search(
                r"(?i)app|router|bp|blueprint|api", owner
            ):
                continue
            path = self.resolve(mod, dec.args[0]).value if dec.args else None
            if not isinstance(path, str):
                continue
            methods = [method.upper()]
            if method in ("route", "api_route"):
                kw = {k.arg: k.value for k in dec.keywords if k.arg}
                m = kw.get("methods")
                methods = (
                    [
                        e.value.upper()
                        for e in m.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    ]
                    if isinstance(m, (ast.List, ast.Tuple))
                    else ["GET"]
                )
            for m_ in methods:
                self._emit(
                    "route",
                    node_key(NodeKind.route, f"{m_} {path}"),
                    {"method": m_, "path": path, "handler_key": fkey, "framework_owner": owner},
                    mod,
                    dec,
                    symbol=info.qualname,
                )

    # llm calls -------------------------------------------------------------

    def _llm_api(self, mod: ModInfo, d: str) -> tuple[str | None, str | None]:
        """Return (api_name, client_var) if dotted callee `d` is an LLM call."""
        for suffix, api in LLM_CALL_SUFFIXES.items():
            if d.endswith("." + suffix):
                root = d.split(".")[0]
                return api, root
        parts = d.split(".")
        if len(parts) == 2 and (parts[0], parts[1]) in LLM_FUNCS:
            return LLM_FUNCS[(parts[0], parts[1])], None
        if len(parts) == 1 and parts[0] in mod.imports:
            origin = mod.imports[parts[0]]
            if (origin[0], origin[1]) in LLM_FUNCS:
                return LLM_FUNCS[(origin[0], origin[1] or "")], None
        return None, None

    def _client_for(self, mod: ModInfo, var: str | None) -> tuple[ModInfo, str] | None:
        if not var:
            return None
        if var in mod.clients:
            return mod, var
        if var in mod.imports:
            origin_mod, origin_name = mod.imports[var]
            target = self._find_module(origin_mod)
            if target and origin_name in target.clients:
                return target, origin_name  # type: ignore[return-value]
        return None

    def _llm_calls(self, mod: ModInfo, info: FuncInfo, fkey: str) -> None:
        for node in ast.walk(info.node):
            if not isinstance(node, ast.Call):
                continue
            d = dotted(node.func) or ""
            api, client_var = self._llm_api(mod, d)
            if not api:
                continue
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            model = self.resolve(mod, kw.get("model"), func=info)
            stream = (
                self.resolve(mod, kw.get("stream"), func=info)
                if "stream" in kw
                else Resolved("literal", api.endswith(".stream"))
            )
            client = self._client_for(mod, client_var)
            endpoint_key = (
                node_key(NodeKind.endpoint, client[0].file.path, client[1]) if client else None
            )
            params = {}
            for p in (
                "max_tokens",
                "max_completion_tokens",
                "temperature",
                "top_p",
                "max_output_tokens",
            ):
                if p in kw:
                    params[p] = self.resolve(mod, kw[p], func=info).display()
            line = node.lineno
            self._emit(
                "llm_call",
                node_key(NodeKind.component, mod.file.path, f"{info.qualname}@L{line}"),
                {
                    "api": api,
                    "function_key": fkey,
                    "model": model.display(),
                    "model_effective": model.effective(),
                    "model_env": model.env,
                    "stream": stream.effective() if stream.kind in ("literal", "env") else None,
                    "stream_display": stream.display(),
                    "structured_output": "response_format" in kw
                    or "text_format" in kw
                    or api.endswith(".parse"),
                    "tools_passed": "tools" in kw or "functions" in kw,
                    "has_timeout": "timeout" in kw or "request_timeout" in kw,
                    "endpoint_key": endpoint_key,
                    "params": params,
                },
                mod,
                node,
                symbol=info.qualname,
            )

    # retrievers ------------------------------------------------------------

    def _retriever(
        self, mod: ModInfo, info: FuncInfo, fkey: str, imported_modules: set[str]
    ) -> None:
        lib = next(
            (
                RETRIEVAL_MODULES[m.split(".")[0]]
                for m in imported_modules
                if m.split(".")[0] in RETRIEVAL_MODULES
            ),
            None,
        )
        store = None
        for d, _ in info.calls:
            last = d.split(".")[-1]
            if last in RETRIEVAL_CALLS or (lib and last in GENERIC_RETRIEVAL_CALLS and "." in d):
                store = RETRIEVAL_CALLS.get(last, lib)
                break
        if store is None:
            return
        topk_param = next(
            (p for p in info.params if p in ("top_k", "k", "n_results", "limit")), None
        )
        self._emit(
            "retriever",
            node_key(NodeKind.retriever, mod.file.path, info.qualname),
            {"store": lib or store, "function_key": fkey, "top_k_param": topk_param},
            mod,
            info.node,
            symbol=info.qualname,
        )

    # side effects / tools -------------------------------------------------

    def _side_effect_kind(self, mod: ModInfo, d: str, node: ast.Call) -> str | None:
        parts = d.split(".")
        root, last = parts[0], parts[-1]
        root_origin = mod.imports.get(root, (root, None))[0].split(".")[0]
        if root in mod.consts and isinstance(mod.consts[root], ast.Call):
            # module-level client object, e.g. `http = httpx.Client()`
            ctor = (dotted(mod.consts[root].func) or "").split(".")[0]  # type: ignore[union-attr]
            root_origin = mod.imports.get(ctor, (ctor, None))[0].split(".")[0]
        if last in HTTP_WRITE_METHODS and root_origin in HTTP_MODULES:
            return "external"
        if root_origin in ("smtplib",) or last in ("send_email", "send_mail", "sendmail"):
            return "external"
        if root_origin in ("stripe",) and last in ("create", "modify", "delete", "refund"):
            return "external"
        if root_origin in ("subprocess",) or d in ("os.system", "os.popen"):
            return "external"
        if last in (
            "commit",
            "insert_one",
            "insert_many",
            "update_one",
            "update_many",
            "delete_one",
            "delete_many",
            "bulk_write",
        ):
            return "write"
        if last == "execute" and node.args:
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and re.match(r"(?is)\s*(insert|update|delete|drop|alter|create)\b", first.value)
            ):
                return "write"
        if d == "open" and len(node.args) >= 2:
            mode = node.args[1]
            if (
                isinstance(mode, ast.Constant)
                and isinstance(mode.value, str)
                and any(c in mode.value for c in "wax")
            ):
                return "file_write"
        if last == "open" and node.args:  # Path.open("a")
            mode = node.args[0]
            if (
                isinstance(mode, ast.Constant)
                and isinstance(mode.value, str)
                and any(c in mode.value for c in "wax")
            ):
                return "file_write"
        return None

    def _side_effects(self, mod: ModInfo, info: FuncInfo, fkey: str) -> None:
        effects: list[tuple[str, str, int]] = []
        for node in ast.walk(info.node):
            if isinstance(node, ast.Call):
                d = dotted(node.func) or ""
                k = self._side_effect_kind(mod, d, node)
                if k:
                    effects.append((k, d, node.lineno))
        if not effects:
            return
        observability = bool(
            LOGGING_NAME.search(info.qualname) or LOGGING_NAME.search(mod.name.split(".")[-1])
        )
        kinds = {k for k, _, _ in effects}
        side_effect = "external" if "external" in kinds else "write"
        gate = self._approval_gate(info, effects)
        self._emit(
            "side_effect_function",
            node_key(NodeKind.tool, mod.file.path, info.qualname),
            {
                "function_key": fkey,
                "name": info.qualname.split(".")[-1],
                "side_effect": side_effect,
                "effects": [{"kind": k, "call": c, "line": ln} for k, c, ln in effects],
                "observability_only": observability and kinds <= {"file_write"},
                "approval_gate": gate["present"],
                "approval_gate_detail": gate,
                "heuristic": True,
            },
            mod,
            info.node,
            symbol=info.qualname,
            observation=Observation.inference,
        )

    @staticmethod
    def _approval_gate(info: FuncInfo, effects: list[tuple[str, str, int]]) -> dict[str, Any]:
        """An approval gate = an approval-like parameter whose falsy value exits (raise/return)
        before the first side-effect call."""
        approval = [p for p in info.params if APPROVAL_PARAMS.match(p)]
        first_effect_line = min(ln for _, _, ln in effects)
        for node in ast.walk(info.node):
            if not isinstance(node, ast.If) or node.lineno >= first_effect_line:
                continue
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            gate_names = names & set(approval)
            exits = any(isinstance(n, (ast.Raise, ast.Return)) for n in node.body)
            if gate_names and exits:
                return {"present": True, "param": sorted(gate_names)[0], "guard_line": node.lineno}
        return {"present": False, "approval_params": approval}

    # reliability -----------------------------------------------------------

    def _reliability(self, mod: ModInfo, info: FuncInfo, fkey: str) -> None:
        for dec in info.node.decorator_list:
            d = dotted(dec.func if isinstance(dec, ast.Call) else dec) or ""
            if d.split(".")[-1] in ("retry", "on_exception", "retry_async"):
                self._emit("retry", fkey, {"decorator": d}, mod, dec, symbol=info.qualname)

    # config access ---------------------------------------------------------

    @staticmethod
    def _subscript_chain(node: ast.expr) -> tuple[str | None, list[str]]:
        """cfg["a"]["b"] -> ("cfg", ["a", "b"]); non-constant keys end the chain."""
        keys: list[str] = []
        while isinstance(node, ast.Subscript):
            sl = node.slice
            if not (isinstance(sl, ast.Constant) and isinstance(sl.value, str)):
                return None, []
            keys.append(sl.value)
            node = node.value
        if isinstance(node, ast.Name):
            return node.id, list(reversed(keys))
        return None, []

    def _config_access(self, mod: ModInfo, info: FuncInfo, fkey: str) -> None:
        """Record constant-key subscript chains (``cfg["retrieval"]["top_k"]``) so config
        keys can be linked to the code that reads them. Local aliases such as
        ``gen = cfg["generation"]`` are followed within the function."""
        aliases: dict[str, list[str]] = {}
        for node in ast.walk(info.node):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                root, keys = self._subscript_chain(node.value)
                if root and keys:
                    aliases[node.targets[0].id] = aliases.get(root, []) + keys
        seen: set[str] = set()
        for node in ast.walk(info.node):
            if not isinstance(node, ast.Subscript) or isinstance(
                getattr(node, "ctx", None), ast.Store
            ):
                continue
            root, keys = self._subscript_chain(node)
            if not root or not keys:
                continue
            full = aliases.get(root, []) + keys
            keypath = ".".join(full)
            if keypath in seen:
                continue
            # only keep maximal chains: skip a prefix of a longer chain already seen
            seen.add(keypath)
            self._emit(
                "config_access",
                fkey,
                {"keypath": keypath, "root": root},
                mod,
                node,
                symbol=info.qualname,
            )

    # call graph ------------------------------------------------------------

    def _call_edges(self, mod: ModInfo, info: FuncInfo, fkey: str) -> None:
        seen: set[str] = set()
        for d, line in info.calls:
            target = self._resolve_callee(mod, d)
            if target and target != fkey and target not in seen:
                seen.add(target)
                self.facts.append(
                    Fact(
                        kind="call_edge",
                        key=fkey,
                        data={"callee_key": target, "line": line},
                        locator=Locator(
                            path=mod.file.path, line_start=line, line_end=line, symbol=info.qualname
                        ),
                        excerpt=redact(mod.lines[line - 1].strip())[:200]
                        if 0 < line <= len(mod.lines)
                        else "",
                        extractor=f"{EXTRACTOR}.call_edge",
                    )
                )

    def _resolve_callee(self, mod: ModInfo, d: str) -> str | None:
        parts = d.split(".")
        if len(parts) == 1:
            if parts[0] in mod.funcs:
                return self._func_key(mod, parts[0])
            if parts[0] in mod.imports:
                origin_mod, origin_name = mod.imports[parts[0]]
                target = self._find_module(origin_mod)
                if target and origin_name in target.funcs:
                    return self._func_key(target, origin_name)  # type: ignore[arg-type]
            return None
        if len(parts) == 2 and parts[0] in mod.imports:
            origin_mod, origin_name = mod.imports[parts[0]]
            target = self._find_module(f"{origin_mod}.{origin_name}" if origin_name else origin_mod)
            if target and parts[1] in target.funcs:
                return self._func_key(target, parts[1])
        return None


def extract_python(inventory: Inventory) -> list[Fact]:
    return PythonExtractor(inventory).run()
