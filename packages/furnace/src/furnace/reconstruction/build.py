"""Deterministic reconstruction: facts -> reconciled claims, AppSpec, and the
Behavior-to-Code Reliability Graph.

Semantic enrichment (purpose prose, human workflow names, failure-mode
candidates) is layered on later by the LLM synthesis step, which may only add
`llm`-sourced candidates; it cannot overwrite what this module derived from code.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from furnace.code_intel import configs, docs, python_ast
from furnace.code_intel.facts import Fact, FactSet
from furnace.code_intel.inventory import Inventory, build_inventory
from furnace.code_intel.signatures import API_HOSTS, ENGINE_PORTS
from furnace.contracts.appspec import (
    AppSpec,
    Architecture,
    Contradiction,
    DynamicSegment,
    Endpoint,
    ExistingReliability,
    LLMCallSite,
    PromptInfo,
    RAGInfo,
    Retriever,
    Route,
    ServingEngine,
    SideEffect,
    Tool,
    Workflow,
)
from furnace.contracts.common import Claim, ClaimStatus, Locator, Method, Observation
from furnace.contracts.graph import EdgeKind, Graph, GraphEdge, GraphNode, NodeKind, node_key
from furnace.reconstruction.reconcile import Candidate, ClaimRec, reconcile

LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}  # noqa: S104 - compared, never bound


@dataclass
class Reconstruction:
    inventory: Inventory
    facts: FactSet
    claims: list[ClaimRec] = field(default_factory=list)
    appspec: AppSpec = field(default_factory=AppSpec)
    graph: Graph = field(default_factory=Graph)


def _claim(recs: list[ClaimRec], fact_uuid: dict[str, Any]) -> Claim[Any] | None:
    """Primary (highest-confidence) ClaimRec as a contract Claim, alternatives attached."""
    if not recs:
        return None
    top = recs[0]
    return Claim(
        value=top.value,
        confidence=top.confidence,
        observation=top.observation,
        method=top.method,
        evidence_ids=[fact_uuid[f] for f in top.supports if f in fact_uuid],
        contradicted_by=[fact_uuid[f] for f in top.contradicts if f in fact_uuid],
        status=top.status,
        alternatives=[
            {
                "value": r.value,
                "confidence": r.confidence,
                "sources": r.sources,
                "evidence": r.supports,
            }
            for r in recs[1:]
        ],
    )


class Builder:
    def __init__(
        self, inv: Inventory, facts: FactSet, fact_uuid: dict[str, Any] | None = None
    ) -> None:
        self.inv = inv
        self.fs = facts
        self.fact_uuid = fact_uuid or {}
        self.claims: list[ClaimRec] = []
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[tuple[str, str, str], GraphEdge] = {}
        self.k = defaultdict(list)
        for f in facts.facts:
            self.k[f.kind].append(f)

    # ------------------------------------------------------------------ helpers

    def _record(self, recs: list[ClaimRec]) -> list[ClaimRec]:
        self.claims.extend(recs)
        return recs

    def _ev(self, *facts: Fact) -> list[Any]:
        return [self.fact_uuid[f.id] for f in facts if f.id in self.fact_uuid]

    def node(
        self,
        kind: NodeKind,
        key: str,
        label: str,
        attrs: dict[str, Any] | None = None,
        confidence: float = 1.0,
        facts: list[Fact] | None = None,
    ) -> str:
        if key not in self.nodes:
            self.nodes[key] = GraphNode(
                kind=kind,
                key=key,
                label=label,
                attrs=attrs or {},
                confidence=confidence,
                evidence_ids=self._ev(*(facts or [])),
            )
        else:
            self.nodes[key].attrs.update(attrs or {})
        return key

    def edge(
        self,
        kind: EdgeKind,
        src: str,
        dst: str,
        confidence: float = 1.0,
        facts: list[Fact] | None = None,
        **attrs: Any,
    ) -> None:
        if src not in self.nodes or dst not in self.nodes:
            return
        self.edges.setdefault(
            (kind.value, src, dst),
            GraphEdge(
                kind=kind,
                src_key=src,
                dst_key=dst,
                confidence=confidence,
                attrs=attrs,
                evidence_ids=self._ev(*(facts or [])),
            ),
        )

    # ------------------------------------------------------------------ endpoint / model

    def _serving_for(self, base_url: str | None) -> tuple[Fact | None, str | None, str]:
        """Match a client base_url to a compose serving service. Returns (serving fact, engine, rationale)."""
        if not base_url:
            return None, None, ""
        parts = urlsplit(base_url)
        host, port = (parts.hostname or "").lower(), parts.port
        for sf in self.k["serving_config"]:
            svc = sf.data["service"].lower()
            if host == svc:
                return sf, sf.data["engine"], f"base_url host '{host}' is compose service '{svc}'"
            if host in LOCAL_HOSTS and port and any(p["host"] == port for p in sf.data["ports"]):
                return (
                    sf,
                    sf.data["engine"],
                    f"base_url port {port} is published by compose service '{svc}'",
                )
        if host in API_HOSTS:
            return None, API_HOSTS[host], f"base_url host {host}"
        if port in ENGINE_PORTS:
            return None, ENGINE_PORTS[port], f"default port {port} of {ENGINE_PORTS[port]}"
        return None, None, ""

    def endpoints(self) -> dict[str, Endpoint]:
        out: dict[str, Endpoint] = {}
        doc_engines = self.k["doc_engine_mention"]
        for cf in self.k["llm_client"]:
            base = cf.data.get("base_url_effective")
            cands: list[Candidate] = []
            sf, engine, why = self._serving_for(base)
            if engine:
                src = "config" if sf else "ast"
                cands.append(
                    Candidate(
                        engine, src, [cf.id] + ([sf.id] if sf else []), why, direct=sf is None
                    )
                )
            elif base is None and cf.data.get("sdk") in ("openai", "anthropic", "groq", "ollama"):
                sdk = cf.data["sdk"]
                cands.append(
                    Candidate(
                        sdk,
                        "ast",
                        [cf.id],
                        f"{cf.data['class']} client without base_url uses the {sdk} API",
                    )
                )
            elif base:
                cands.append(
                    Candidate(
                        "unknown",
                        "ast",
                        [cf.id],
                        f"self-hosted endpoint {base}; engine not identifiable from code",
                    )
                )
            for d in doc_engines:
                cands.append(
                    Candidate(
                        d.data["engine"],
                        "readme",
                        [d.id],
                        f"{d.data['path']} mentions {d.data['engine']}",
                    )
                )
            recs = self._record(reconcile(cf.key, "serving_engine", cands))
            claim = _claim(recs, self.fact_uuid)
            engine_value = (
                ServingEngine(claim.value)
                if claim and claim.value in ServingEngine.__members__
                else ServingEngine.unknown
            )
            if claim:
                claim = claim.model_copy(update={"value": engine_value})
            out[cf.key] = Endpoint(
                key=cf.key,
                base_url_ref=cf.data.get("base_url"),
                engine=claim
                or Claim(
                    value=ServingEngine.unknown,
                    confidence=0.3,
                    observation=Observation.inference,
                    method=Method.deterministic,
                ),
                serving_flags=(sf.data["flags"] if sf else {}),
                locator=cf.locator,
            )
            self.node(
                NodeKind.endpoint,
                cf.key,
                f"{cf.data['class']} → {base or 'SDK default'}",
                {
                    "base_url": cf.data.get("base_url"),
                    "engine": engine_value.value,
                    "has_timeout": cf.data.get("has_timeout"),
                },
                claim.confidence if claim else 0.3,
                [cf],
            )
            if sf:
                self.node(
                    NodeKind.serving_config,
                    sf.key,
                    f"{sf.data['engine']} · {sf.data['service']}",
                    {
                        "engine": sf.data["engine"],
                        "flags": sf.data["flags"],
                        "model": sf.data["model"],
                        "image": sf.data["image"],
                    },
                    0.95,
                    [sf],
                )
                self.edge(EdgeKind.configured_by, cf.key, sf.key, 0.9, [cf, sf], reason=why)
        return out

    def _served_model(self, call: Fact) -> tuple[Any, list[Fact], str] | None:
        """If the code's model id is a served alias of a compose serving config, resolve it."""
        alias = call.data.get("model_effective")
        ep = call.data.get("endpoint_key")
        client = next((f for f in self.k["llm_client"] if f.key == ep), None)
        if not client:
            return None
        sf, _, why = self._serving_for(client.data.get("base_url_effective"))
        if not sf or not sf.data.get("model"):
            return None
        served = sf.data["flags"].get("served-model-name")
        if alias is None or served is None or str(alias) == str(served):
            return (
                sf.data["model"],
                [client, sf],
                f"code requests '{alias}', which {sf.data['service']} serves as {sf.data['model']} ({why})",
            )
        return None

    def llm_calls(self, endpoints: dict[str, Endpoint]) -> tuple[list[LLMCallSite], list[ClaimRec]]:
        sites: list[LLMCallSite] = []
        app_model_cands: list[Candidate] = []
        for c in self.k["llm_call"]:
            if self._is_test_file(c.locator.path):
                continue  # counted as existing evals, not as an app call site
            cands: list[Candidate] = []
            served = self._served_model(c)
            if served:
                model, extra, why = served
                cands.append(Candidate(model, "config", [c.id] + [f.id for f in extra], why))
            elif c.data.get("model_effective") is not None:
                cands.append(
                    Candidate(c.data["model_effective"], "ast", [c.id], f"model={c.data['model']}")
                )
            model_claim = _claim(self._record(reconcile(c.key, "model", cands)), self.fact_uuid)
            app_model_cands.extend(cands)
            stream_claim = None
            if c.data.get("stream") is not None:
                stream_claim = _claim(
                    self._record(
                        reconcile(
                            c.key,
                            "streaming",
                            [
                                Candidate(
                                    bool(c.data["stream"]),
                                    "ast",
                                    [c.id],
                                    f"stream={c.data['stream_display']}",
                                )
                            ],
                        )
                    ),
                    self.fact_uuid,
                )
            provider = None
            ep = endpoints.get(c.data.get("endpoint_key") or "")
            if ep:
                provider = Claim(
                    value=ep.engine.value.value
                    if hasattr(ep.engine.value, "value")
                    else str(ep.engine.value),
                    confidence=ep.engine.confidence,
                    observation=ep.engine.observation,
                    method=ep.engine.method,
                    evidence_ids=ep.engine.evidence_ids,
                )
            sites.append(
                LLMCallSite(
                    key=c.key,
                    locator=c.locator,
                    api=c.data["api"],
                    provider=provider,
                    model=model_claim,
                    streaming=stream_claim,
                    structured_output=c.data["structured_output"],
                    tools_passed=c.data["tools_passed"],
                    params=c.data.get("params", {}),
                    endpoint_key=c.data.get("endpoint_key"),
                    has_timeout=bool(
                        c.data["has_timeout"] or (self._client_fact(c) or {}).get("has_timeout")
                    ),
                )
            )
            fn = c.data["function_key"]
            self.node(
                NodeKind.component,
                c.key,
                f"LLM call · {c.data['api'].split('.', 1)[-1]}",
                {
                    "api": c.data["api"],
                    "stream": c.data.get("stream"),
                    "has_timeout": sites[-1].has_timeout,
                    "path": c.locator.path,
                    "line": c.locator.line_start,
                },
                1.0,
                [c],
            )
            self.edge(EdgeKind.calls, fn, c.key, 1.0, [c])
            if model_claim:
                mkey = node_key(NodeKind.model, str(model_claim.value))
                self.node(
                    NodeKind.model,
                    mkey,
                    str(model_claim.value),
                    {"alias": c.data.get("model_effective")},
                    model_claim.confidence,
                )
                self.edge(EdgeKind.uses_model, c.key, mkey, model_claim.confidence, [c])
                if c.data.get("endpoint_key") in self.nodes:
                    self.edge(EdgeKind.served_by, mkey, c.data["endpoint_key"], 0.9, [c])
        # app-level model: code-derived values vs. what the docs say
        code_models = {str(c.value).strip().lower() for c in app_model_cands}
        for d in self.k["doc_model_mention"]:
            app_model_cands.append(
                Candidate(
                    d.data["model"],
                    "readme",
                    [d.id],
                    f"{d.data['path']}:{d.locator.line_start} says '{d.data['model']}'",
                )
            )
        if len(code_models) > 1 and not any(
            c.source == "readme" and str(c.value).strip().lower() not in code_models
            for c in app_model_cands
        ):
            # Several models in code is a multi-model app, not a disagreement; only a documented
            # model that matches none of them contradicts the code.
            return sites, []
        app_model = self._record(reconcile("app", "model", app_model_cands))
        return sites, app_model

    def _client_fact(self, call: Fact) -> dict[str, Any] | None:
        f = next((f for f in self.k["llm_client"] if f.key == call.data.get("endpoint_key")), None)
        return f.data if f else None

    # ------------------------------------------------------------------ components / graph

    @staticmethod
    def _non_app_path(key: str) -> bool:
        return key.startswith(("component:tests/", "component:test_", "component:scripts/"))

    @staticmethod
    def _is_test_file(path: str | None) -> bool:
        """Test code: evaluation assets, not the app's own call sites or prompts."""
        if not path:
            return False
        parts = path.split("/")
        name = parts[-1]
        return (
            "tests" in parts[:-1]
            or "test" in parts[:-1]
            or name.startswith("test_")
            or name.endswith("_test.py")
            or name == "conftest.py"
        )

    def _compute_route_reach(self) -> None:
        """All functions reachable from any route handler through the call graph."""
        callees: dict[str, set[str]] = defaultdict(set)
        for e in self.k["call_edge"]:
            callees[e.key].add(e.data["callee_key"])
        self.callees = callees
        seen: set[str] = set()
        todo = [r.data["handler_key"] for r in self.k["route"]]
        while todo:
            n = todo.pop()
            if n in seen:
                continue
            seen.add(n)
            todo.extend(callees.get(n, ()))
        self.route_reach = seen

    def is_action(self, f: Fact) -> bool:
        """A side-effecting function counts as an application action (tool) when a request
        path can reach it; without routes, any non-test, non-script function qualifies."""
        if f.data["observability_only"]:
            return False
        if self.k["route"]:
            return f.data["function_key"] in self.route_reach
        return not self._non_app_path(f.data["function_key"])

    def components(self) -> None:
        """Add component nodes for functions on any route -> interesting-function path."""
        self._compute_route_reach()
        funcs = {f.key: f for f in self.k["function"]}
        callees = self.callees
        # Always relevant (even outside request paths, e.g. CLI apps): LLM calls, retrieval, prompts.
        core: set[str] = set()
        core |= {c.data["function_key"] for c in self.k["llm_call"]}
        core |= {r.data["function_key"] for r in self.k["retriever"]}
        core |= {u.key for u in self.k["uses_prompt"]}
        core |= {s.data["component_key"] for s in self.k["system_message"]}
        # Relevant only on a request path: actions and config reads.
        gated = {
            t.data["function_key"] for t in self.k["side_effect_function"] if self.is_action(t)
        }
        gated |= {
            a.key
            for a in self.k["config_access"]
            if (a.key in self.route_reach if self.k["route"] else not self._non_app_path(a.key))
        }
        interesting = core | gated

        def reaches(start: str) -> set[str]:
            keep: set[str] = set()
            memo: dict[str, bool] = {}

            def dfs(n: str, stack: set[str]) -> bool:
                if n in memo:
                    return memo[n]
                if n in stack:
                    return False
                hit = n in interesting
                for m in callees.get(n, ()):
                    if dfs(m, stack | {n}):
                        hit = True
                memo[n] = hit
                if hit:
                    keep.add(n)
                return hit

            dfs(start, set())
            return keep

        keep: set[str] = set()
        for r in self.k["route"]:
            keep |= reaches(r.data["handler_key"])
        keep |= {k for k in interesting if not self._non_app_path(k)}
        for key in keep:
            f = funcs.get(key)
            if f is None:
                continue
            self.node(
                NodeKind.component,
                key,
                f.data["qualname"],
                {"path": f.locator.path, "line": f.locator.line_start},
                1.0,
                [f],
            )
        for e in self.k["call_edge"]:
            self.edge(EdgeKind.calls, e.key, e.data["callee_key"], 1.0, [e])

    def routes(self) -> list[Route]:
        out: list[Route] = []
        for r in self.k["route"]:
            self.node(
                NodeKind.route,
                r.key,
                f"{r.data['method']} {r.data['path']}",
                {"method": r.data["method"], "path": r.data["path"]},
                1.0,
                [r],
            )
            self.edge(EdgeKind.routes_to, r.key, r.data["handler_key"], 1.0, [r])
            out.append(
                Route(
                    key=r.key,
                    method=r.data["method"],
                    path=r.data["path"],
                    handler=r.data["handler_key"],
                    locator=r.locator,
                )
            )
        return out

    def prompts(self) -> list[PromptInfo]:
        out: list[PromptInfo] = []
        for p in self.k["prompt"]:
            if self._is_test_file(p.locator.path):
                continue
            self.node(
                NodeKind.prompt,
                p.key,
                p.data["name"],
                {
                    "static_chars": p.data["static_chars"],
                    "approx_tokens": p.data["approx_tokens"],
                    "inline": True,
                    "path": p.locator.path,
                    "line": p.locator.line_start,
                },
                1.0,
                [p],
            )
            out.append(
                PromptInfo(
                    key=p.key,
                    locator=p.locator,
                    static_chars=p.data["static_chars"],
                    static_tokens=p.data["approx_tokens"],
                )
            )
        for s in self.k["system_message"]:
            segs = [
                DynamicSegment(name=d["name"], char_offset=d["char_offset"])
                for d in s.data["dynamic_segments"]
            ]
            self.node(
                NodeKind.prompt,
                s.key,
                f"system message · {s.data['function']}",
                {
                    "static_chars": s.data["static_chars"],
                    "static_prefix_chars": s.data["static_prefix_chars"],
                    "dynamic_head": s.data["dynamic_head"],
                    "dynamic_segments": [d.model_dump() for d in segs],
                    "path": s.locator.path,
                    "line": s.locator.line_start,
                },
                1.0,
                [s],
            )
            self.edge(EdgeKind.uses_prompt, s.data["component_key"], s.key, 1.0, [s])
            for p in self.k["prompt"]:
                if p.data["name"] in s.data["references"]:
                    self.edge(EdgeKind.depends_on, s.key, p.key, 1.0, [s, p])
            out.append(
                PromptInfo(
                    key=s.key,
                    locator=s.locator,
                    static_chars=s.data["static_chars"],
                    static_tokens=round(s.data["static_chars"] / 4),
                    dynamic_segments=segs,
                    dynamic_head=s.data["dynamic_head"],
                )
            )
        for u in self.k["uses_prompt"]:
            self.edge(EdgeKind.uses_prompt, u.key, u.data["prompt_key"], 1.0, [u])
        return out

    def rag(self) -> RAGInfo:
        cands: list[Candidate] = []
        retrievers: list[Retriever] = []
        for r in self.k["retriever"]:
            cands.append(
                Candidate(
                    True, "ast", [r.id], f"{r.locator.short()} queries a {r.data['store']} index"
                )
            )
            store = _claim(
                self._record(
                    reconcile(r.key, "retrieval_store", [Candidate(r.data["store"], "ast", [r.id])])
                ),
                self.fact_uuid,
            )
            assert store is not None  # one candidate always yields one claim
            topk = self._topk_claim(r)
            retrievers.append(Retriever(key=r.key, locator=r.locator, store=store, top_k=topk))
            self.node(
                NodeKind.retriever,
                r.key,
                f"{r.data['store']} retriever",
                {
                    "store": r.data["store"],
                    "top_k": topk.value if topk else None,
                    "path": r.locator.path,
                },
                0.95,
                [r],
            )
            self.edge(EdgeKind.retrieves_via, r.data["function_key"], r.key, 0.95, [r])
        for d in self.k["dependency"]:
            if d.data["category"] in ("retrieval", "vector_store"):
                cands.append(Candidate(True, "dependency", [d.id], f"depends on {d.data['name']}"))
        for d in self.k["doc_rag_mention"]:
            cands.append(
                Candidate(True, "readme", [d.id], f"{d.data['path']} mentions '{d.data['term']}'")
            )
        if not cands:
            cands.append(
                Candidate(
                    False,
                    "absence",
                    [],
                    "no retriever calls, retrieval dependencies or documentation mentions found",
                )
            )
        present = _claim(self._record(reconcile("app", "uses_rag", cands)), self.fact_uuid)
        assert present is not None
        return RAGInfo(present=present, retrievers=retrievers)

    def _topk_claim(self, r: Fact) -> Claim[int] | None:
        """top_k comes from config when the retriever's caller reads a config key named like top_k."""
        for a in self.k["config_access"]:
            if a.data["keypath"].split(".")[-1] in ("top_k", "k", "n_results"):
                key = next(
                    (c for c in self.k["config_key"] if c.data["keypath"] == a.data["keypath"]),
                    None,
                )
                if key is not None and isinstance(key.data["value"], int):
                    return _claim(
                        self._record(
                            reconcile(
                                r.key,
                                "top_k",
                                [
                                    Candidate(
                                        key.data["value"],
                                        "config",
                                        [a.id, key.id],
                                        f"{a.data['keypath']} = {key.data['value']} in {key.data['file']}",
                                    )
                                ],
                            )
                        ),
                        self.fact_uuid,
                    )
        if isinstance(r.data.get("top_k_literal"), int):
            return _claim(
                self._record(
                    reconcile(
                        r.key,
                        "top_k",
                        [
                            Candidate(
                                r.data["top_k_literal"],
                                "ast",
                                [r.id],
                                f"k={r.data['top_k_literal']} at the retrieval call",
                            )
                        ],
                    )
                ),
                self.fact_uuid,
            )
        return None

    def config_links(self) -> None:
        by_keypath = {c.data["keypath"]: c for c in self.k["config_key"]}
        for a in self.k["config_access"]:
            ck = by_keypath.get(a.data["keypath"])
            if ck is None or a.key not in self.nodes:
                continue
            self.node(
                NodeKind.config_key,
                ck.key,
                f"{ck.data['file']}#{ck.data['keypath']}",
                {"file": ck.data["file"], "keypath": ck.data["keypath"], "value": ck.data["value"]},
                0.95,
                [ck],
            )
            self.edge(EdgeKind.configured_by, a.key, ck.key, 0.95, [a, ck])
        for sf in self.k["serving_config"]:
            for flag, value in sf.data["flags"].items():
                key = node_key(
                    NodeKind.config_key, f"{sf.locator.path}#{sf.data['service']}.--{flag}"
                )
                if sf.key in self.nodes:
                    self.node(
                        NodeKind.config_key,
                        key,
                        f"--{flag}",
                        {
                            "file": sf.locator.path,
                            "keypath": f"{sf.data['service']}.--{flag}",
                            "value": value,
                        },
                        0.95,
                        [sf],
                    )
                    self.edge(EdgeKind.configured_by, sf.key, key, 0.95, [sf])

    def tools(self) -> list[Tool]:
        out: list[Tool] = []
        for t in self.k["side_effect_function"]:
            if not self.is_action(t):
                continue
            se = SideEffect(t.data["side_effect"])
            effects = ", ".join(f"{e['call']} (line {e['line']})" for e in t.data["effects"])
            se_claim = _claim(
                self._record(
                    reconcile(
                        t.key,
                        "side_effect",
                        [Candidate(se.value, "ast", [t.id], f"calls {effects}")],
                    )
                ),
                self.fact_uuid,
            )
            gate = t.data["approval_gate_detail"]
            if gate["present"]:
                gate_cand = Candidate(
                    True,
                    "ast_heuristic",
                    [t.id],
                    f"'if not {gate['param']}' exits before the side effect (line {gate['guard_line']})",
                    direct=False,
                )
            else:
                gate_cand = Candidate(
                    False,
                    "absence",
                    [t.id],
                    "no approval parameter guards the side effect",
                    direct=False,
                )
            gate_claim = _claim(
                self._record(reconcile(t.key, "approval_gate", [gate_cand])), self.fact_uuid
            )
            assert se_claim and gate_claim
            out.append(
                Tool(
                    key=t.key,
                    name=t.data["name"],
                    locator=t.locator,
                    side_effect=se_claim.model_copy(update={"value": se}),
                    approval_gate=gate_claim,
                )
            )
            self.node(
                NodeKind.tool,
                t.key,
                t.data["name"],
                {
                    "side_effect": se.value,
                    "approval_gate": gate["present"],
                    "path": t.locator.path,
                    "line": t.locator.line_start,
                },
                se_claim.confidence,
                [t],
            )
            self.edge(EdgeKind.invokes_tool, t.data["function_key"], t.key, 0.95, [t])
            if gate["present"]:
                bkey = node_key(
                    NodeKind.security_boundary, t.locator.path or "", f"{t.data['name']}#approval"
                )
                self.node(
                    NodeKind.security_boundary,
                    bkey,
                    f"approval gate · {gate['param']}",
                    {"kind": "approval_gate", "param": gate["param"], "line": gate["guard_line"]},
                    gate_claim.confidence,
                    [t],
                )
                self.edge(EdgeKind.guarded_by, t.key, bkey, gate_claim.confidence, [t])
        return out

    def reliability(self, sites: list[LLMCallSite]) -> ExistingReliability:
        rel = ExistingReliability()

        def one(
            subject: str,
            predicate: str,
            value: str,
            source: str,
            facts: list[Fact],
            why: str,
            direct: bool = True,
        ) -> Claim[str]:
            claim = _claim(
                self._record(
                    reconcile(
                        subject,
                        predicate,
                        [Candidate(value, source, [f.id for f in facts], why, direct)],
                    )
                ),
                self.fact_uuid,
            )
            assert claim is not None  # one candidate always yields one claim
            return claim

        tests = self.k["test_file"]
        if tests:
            c = one(
                "app",
                "has_tests",
                f"{len(tests)} test files",
                "ast",
                tests,
                ", ".join(t.locator.path or "" for t in tests[:5]),
            )
            rel.tests.append(c)
        test_calls = [f for f in self.k["llm_call"] if self._is_test_file(f.locator.path)]
        if test_calls:
            rel.evals.append(
                one(
                    "app",
                    "llm_in_tests",
                    f"tests call an LLM ({len(test_calls)} call site(s): live-model or LLM-judged tests)",
                    "ast",
                    test_calls,
                    ", ".join(sorted({f.locator.path or "" for f in test_calls})),
                )
            )
        for d in self.k["dependency"]:
            if d.data["category"] == "eval":
                rel.evals.append(
                    one(
                        "app",
                        "eval_framework",
                        d.data["name"],
                        "dependency",
                        [d],
                        f"depends on {d.data['name']}",
                    )
                )
            if d.data["category"] == "tracing":
                rel.tracing.append(
                    one(
                        "app",
                        "tracing_library",
                        d.data["note"] or d.data["name"],
                        "dependency",
                        [d],
                        f"depends on {d.data['name']}",
                    )
                )
            if d.data["category"] == "retry":
                rel.retries.append(
                    one(
                        "app",
                        "retry_library",
                        d.data["name"],
                        "dependency",
                        [d],
                        f"depends on {d.data['name']}",
                    )
                )
        for t in self.k["tracing_import"]:
            rel.tracing.append(
                one(
                    "app",
                    "tracing_library",
                    t.data["library"],
                    "ast",
                    [t],
                    f"imports {t.data['library']}",
                )
            )
        for t in self.k["side_effect_function"]:
            if t.data["observability_only"]:
                rel.tracing.append(
                    one(
                        "app",
                        "custom_call_log",
                        f"custom log: {t.data['name']}",
                        "ast_heuristic",
                        [t],
                        f"{t.locator.short()} appends records to a file",
                        direct=False,
                    )
                )
        for r in self.k["retry"]:
            rel.retries.append(
                one(r.key, "retry", r.data["decorator"], "ast", [r], f"@{r.data['decorator']}")
            )
        for s in sites:
            if s.has_timeout:
                f = next(x for x in self.k["llm_call"] if x.key == s.key)
                rel.timeouts.append(
                    one(
                        s.key,
                        "timeout",
                        "explicit timeout",
                        "ast",
                        [f],
                        "timeout set on call or client",
                    )
                )
        return rel

    def workflows(self, rag_present: bool) -> list[Workflow]:
        """Deterministic workflows: one per route that reaches LLM / retrieval / tool code."""
        out: list[Workflow] = []
        adj: dict[str, list[str]] = defaultdict(list)
        for kind, s, d in self.edges:
            if kind in (EdgeKind.calls.value, EdgeKind.routes_to.value):
                adj[s].append(d)
        for r in self.k["route"]:
            reach: list[str] = []
            seen = {r.key}
            q = deque([r.key])
            while q:
                n = q.popleft()
                for m in adj.get(n, []):
                    if m not in seen:
                        seen.add(m)
                        reach.append(m)
                        q.append(m)
            llm = [n for n in reach if any(n == c.key for c in self.k["llm_call"])]
            retr = [rt.key for rt in self.k["retriever"] if rt.data["function_key"] in seen]
            tools = [
                t.key
                for t in self.k["side_effect_function"]
                if t.data["function_key"] in seen and not t.data["observability_only"]
            ]
            if not (llm or retr or tools):
                continue
            caps: list[str] = []
            if llm and retr:
                caps.append(
                    self._capability(r, "rag_answer", "Answer from retrieved documents", llm + retr)
                )
            elif llm:
                caps.append(self._capability(r, "llm_generation", "Generate with an LLM", llm))
            for t in tools:
                name = self.nodes[t].label
                caps.append(
                    self._capability(r, f"action_{name}", f"Perform side effect: {name}", [t])
                )
            label = f"{r.data['method']} {r.data['path']}"
            wkey = node_key(NodeKind.workflow, r.locator.path or "", label)
            self.node(
                NodeKind.workflow, wkey, label, {"route": r.key, "deterministic": True}, 0.9, [r]
            )
            for c in caps:
                self.edge(EdgeKind.implements, c, wkey, 0.9)
            steps = [
                self.nodes[n].label
                for n in reach
                if n in self.nodes and self.nodes[n].kind in (NodeKind.component,)
            ]
            out.append(
                Workflow(
                    key=wkey,
                    name=label,
                    description=f"Requests to {label}",
                    steps=steps,
                    route_keys=[r.key],
                    capability_keys=caps,
                    confidence=0.9,
                )
            )
        return out

    def _capability(self, route: Fact, kind: str, label: str, members: list[str]) -> str:
        key = node_key(NodeKind.capability, route.key, kind)
        self.node(NodeKind.capability, key, label, {"kind": kind, "route": route.key}, 0.85)
        for m in members:
            self.edge(EdgeKind.implements, m, key, 0.85)
        self.edge(EdgeKind.implements, route.data["handler_key"], key, 0.9)
        return key

    def contradictions(self) -> list[Contradiction]:
        groups: dict[str, list[ClaimRec]] = defaultdict(list)
        for c in self.claims:
            if c.conflict_group:
                groups[c.conflict_group].append(c)
        out = []
        for recs in groups.values():
            recs.sort(key=lambda r: -r.confidence)
            top = recs[0]
            out.append(
                Contradiction(
                    subject_key=top.subject_key,
                    predicate=top.predicate,
                    values=[
                        {
                            "value": r.value,
                            "confidence": r.confidence,
                            "sources": r.sources,
                            "rationale": r.rationale,
                            "evidence": r.supports,
                        }
                        for r in recs
                    ],
                    note=f"{len(recs)} sources disagree on {top.predicate}; strongest evidence: {', '.join(top.sources)}",
                )
            )
        return out

    # ------------------------------------------------------------------ main

    def build(self) -> tuple[AppSpec, Graph]:
        self.components()
        routes = self.routes()
        endpoints = self.endpoints()
        sites, app_model = self.llm_calls(endpoints)
        prompts = self.prompts()
        rag = self.rag()
        tools = self.tools()
        self.config_links()
        reliability = self.reliability(sites)
        workflows = self.workflows(bool(rag.present.value))
        frameworks: list[Claim[Any]] = []
        for d in self.k["dependency"]:
            if d.data["category"] in ("web", "llm_framework"):
                c = _claim(
                    self._record(
                        reconcile(
                            "app",
                            "framework",
                            [Candidate(d.data["note"] or d.data["name"], "dependency", [d.id])],
                        )
                    ),
                    self.fact_uuid,
                )
                if c:
                    frameworks.append(c)
        title = next(iter(self.k["doc_title"]), None)
        purpose = None
        if title:
            purpose = _claim(
                self._record(
                    reconcile(
                        "app",
                        "purpose",
                        [
                            Candidate(
                                title.data["title"],
                                "readme",
                                [title.id],
                                "README title",
                                direct=False,
                            )
                        ],
                    )
                ),
                self.fact_uuid,
            )
        spec = AppSpec(
            purpose=purpose,
            architecture=Architecture(
                languages=self.inv.languages,
                frameworks=frameworks,
                services=[f.data["service"] for f in self.k["compose_service"]],
                entrypoints=[r.handler or "" for r in routes],
            ),
            workflows=workflows,
            routes=routes,
            llm_calls=sites,
            endpoints=list(endpoints.values()),
            prompts=prompts,
            rag=rag,
            tools=tools,
            reliability_existing=reliability,
            contradictions=self.contradictions(),
        )
        _ = app_model
        graph = Graph(nodes=list(self.nodes.values()), edges=list(self.edges.values()))
        return spec, graph


def collect_facts(root: Path) -> tuple[Inventory, FactSet]:
    inv = build_inventory(root)
    fs = FactSet()
    fs.extend(python_ast.extract_python(inv))
    fs.extend(configs.extract_all(inv))
    fs.extend(docs.extract_docs(inv))
    return inv, fs


def reconstruct(root: Path, fact_uuid: dict[str, Any] | None = None) -> Reconstruction:
    inv, fs = collect_facts(root)
    b = Builder(inv, fs, fact_uuid)
    spec, graph = b.build()
    return Reconstruction(inventory=inv, facts=fs, claims=b.claims, appspec=spec, graph=graph)


def app_level(claims: list[ClaimRec], predicate: str) -> list[ClaimRec]:
    return [c for c in claims if c.subject_key == "app" and c.predicate == predicate]


__all__ = ["ClaimStatus", "Locator", "Reconstruction", "app_level", "collect_facts", "reconstruct"]
