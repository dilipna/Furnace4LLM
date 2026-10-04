from app.prompts import build_context, build_messages
from app.retriever import retrieve


def test_context_has_citation_tags_and_respects_budget():
    chunks = retrieve("How do I pair a controller?", top_k=3)
    ctx = build_context(chunks, max_chars=6000)
    assert "[doc:pairing]" in ctx
    assert len(build_context(chunks, max_chars=50)) <= 50


def test_messages_shape():
    msgs = build_messages("q", retrieve("q", top_k=1), 6000)
    assert [m["role"] for m in msgs] == ["system", "user"]
