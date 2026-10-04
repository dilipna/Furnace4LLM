"""Golden tests: deterministic reconstruction of fixture F1 (support-rag-py)."""

from pathlib import Path

import pytest
from furnace.contracts.appspec import ServingEngine, SideEffect
from furnace.contracts.common import ClaimStatus
from furnace.contracts.graph import EdgeKind, NodeKind
from furnace.reconstruction.build import app_level, reconstruct

F1 = Path(__file__).resolve().parents[3] / "fixtures" / "apps" / "support-rag-py"


@pytest.fixture(scope="module")
def rec():
    return reconstruct(F1)


def test_routes_and_llm_call(rec):
    s = rec.appspec
    assert {f"{r.method} {r.path}" for r in s.routes} == {
        "GET /health",
        "POST /chat",
        "POST /tickets",
    }
    (call,) = s.llm_calls
    assert call.locator.path == "app/llm.py"
    assert call.api == "openai.chat.completions.create"
    assert call.streaming is not None and call.streaming.value is True
    assert call.has_timeout is False


def test_model_alias_resolved_through_compose(rec):
    (call,) = rec.appspec.llm_calls
    assert call.model is not None
    assert call.model.value == "Qwen/Qwen2.5-0.5B-Instruct"


def test_readme_code_model_conflict_is_shown_not_resolved(rec):
    models = app_level(rec.claims, "model")
    values = [m.value for m in models]
    assert values == ["Qwen/Qwen2.5-0.5B-Instruct", "GPT-4o"]  # code first, README second
    assert all(m.status == ClaimStatus.contested for m in models)
    assert models[0].confidence > models[1].confidence
    (contra,) = [c for c in rec.appspec.contradictions if c.predicate == "model"]
    assert {v["value"] for v in contra.values} == {"Qwen/Qwen2.5-0.5B-Instruct", "GPT-4o"}


def test_serving_engine_and_flags(rec):
    (ep,) = rec.appspec.endpoints
    assert ep.engine.value == ServingEngine.vllm
    assert ep.serving_flags["enable-prefix-caching"] is True


def test_rag_retriever_and_top_k_from_config(rec):
    rag = rec.appspec.rag
    assert rag is not None and rag.present.value is True and rag.present.confidence > 0.95
    (r,) = rag.retrievers
    assert r.locator.path == "app/retriever.py" and r.store.value == "bm25"
    assert r.top_k is not None and r.top_k.value == 3


def test_tool_side_effect_and_approval_gate(rec):
    (tool,) = rec.appspec.tools  # log_llm_call is observability, not a tool
    assert tool.name == "create_ticket"
    assert tool.side_effect.value == SideEffect.external
    assert tool.approval_gate.value is True
    assert tool.approval_gate.confidence < tool.side_effect.confidence  # heuristic vs observed


def test_prompt_is_static_and_prefix_stable(rec):
    system = [p for p in rec.appspec.prompts if p.key.endswith("#system")]
    assert system and system[0].dynamic_head is False
    const = [p for p in rec.appspec.prompts if p.key == "prompt:app/prompts.py::SYSTEM_PROMPT"]
    assert const and const[0].static_chars > 3000


def test_existing_reliability(rec):
    rel = rec.appspec.reliability_existing
    assert rel.tests and not rel.timeouts and not rel.retries and not rel.evals
    assert any("log_llm_call" in c.value for c in rel.tracing)


def test_graph_links_prompt_and_config_to_the_chat_workflow(rec):
    g = rec.graph
    kinds = {n.key: n.kind for n in g.nodes}
    edges = {(e.kind, e.src_key, e.dst_key) for e in g.edges}
    assert kinds["route:POST /chat"] == NodeKind.route
    assert (EdgeKind.routes_to, "route:POST /chat", "component:app/main.py::chat") in edges
    assert (
        EdgeKind.uses_prompt,
        "component:app/prompts.py::build_messages",
        "prompt:app/prompts.py::SYSTEM_PROMPT",
    ) in edges
    assert (
        EdgeKind.configured_by,
        "component:app/main.py::chat",
        "config_key:config/rag.yaml#retrieval.top_k",
    ) in edges
    assert (
        EdgeKind.guarded_by,
        "tool:app/tickets.py::create_ticket",
        "security_boundary:app/tickets.py::create_ticket#approval",
    ) in edges


def test_dynamic_head_detected_when_prompt_starts_with_runtime_value(tmp_path):
    """The R1 regression: a request id / timestamp prepended to the system prompt."""
    import shutil

    dst = tmp_path / "f1"
    shutil.copytree(F1, dst, ignore=shutil.ignore_patterns(".venv", "traces"))
    p = dst / "app" / "prompts.py"
    src = p.read_text(encoding="utf-8")
    src = src.replace(
        '{"role": "system", "content": SYSTEM_PROMPT}',
        '{"role": "system", "content": f"Request {request_id} at {now}\\n" + SYSTEM_PROMPT}',
    )
    p.write_text(src, encoding="utf-8")
    rec = reconstruct(dst)
    (system,) = [x for x in rec.appspec.prompts if x.key.endswith("#system")]
    assert system.dynamic_head is True
    assert [d.name for d in system.dynamic_segments] == ["request_id", "now"]
