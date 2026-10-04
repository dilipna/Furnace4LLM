"""What the documentation *claims* about the system (models, engines, RAG).

A README statement is direct evidence of what the README says, but only weak
evidence of what the code does; reconciliation weighs it accordingly and
surfaces conflicts with code instead of picking a winner silently.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from furnace.code_intel.facts import Fact
from furnace.code_intel.inventory import Inventory
from furnace.contracts.common import Locator
from furnace.security.redact import redact

EXTRACTOR = "docs@1"

ARCH_DOC = re.compile(
    r"(?i)(^|/)(readme|architecture|design|overview|system|contributing)[^/]*\.(md|mdx|rst|txt)$"
)

MODEL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "openai",
        re.compile(
            r"\b(gpt-4o(?:-mini)?|gpt-4\.1(?:-mini|-nano)?|gpt-4(?:-turbo)?|gpt-3\.5-turbo|gpt-5(?:\.\d)?(?:-mini|-nano)?|o[134](?:-mini)?)\b",
            re.I,
        ),
    ),
    (
        "anthropic",
        re.compile(
            r"\b(claude[- ](?:opus|sonnet|haiku|fable)?[- ]?[\d.]*[\w.-]*|claude-[\w.-]+)\b", re.I
        ),
    ),
    ("meta", re.compile(r"\b(llama[- ]?\d(?:\.\d)?[\w.-]*)\b", re.I)),
    ("qwen", re.compile(r"\b(qwen[\d.]*(?:-[\w.]+)*)\b", re.I)),
    ("mistral", re.compile(r"\b(mistral[\w.-]*|mixtral[\w.-]*)\b", re.I)),
    ("google", re.compile(r"\b(gemini[\w.-]*|gemma[\w.-]*)\b", re.I)),
    ("deepseek", re.compile(r"\b(deepseek[\w.-]*)\b", re.I)),
]
ENGINE_PATTERNS = {
    "vllm": re.compile(r"\bvllm\b", re.I),
    "sglang": re.compile(r"\bsglang\b", re.I),
    "ollama": re.compile(r"\bollama\b", re.I),
    "tgi": re.compile(r"\btext[- ]generation[- ]inference\b|\bTGI\b"),
    "tensorrt-llm": re.compile(r"\btensorrt[- ]llm\b", re.I),
}
RAG_PATTERN = re.compile(
    r"(?i)\b(retriev\w*|vector (?:store|database|search)|embeddings?|RAG|pgvector|bm25|semantic search|documentation search|knowledge base)\b"
)


def extract_docs(inv: Inventory) -> list[Fact]:
    facts: list[Fact] = []
    for f in inv.files:
        if not f.parseable or not ARCH_DOC.search(f.path):
            continue
        text = inv.read(f)
        for lineno, line in enumerate(text.splitlines(), 1):
            for provider, pat in MODEL_PATTERNS:
                for m in pat.finditer(line):
                    value = m.group(1).strip().rstrip(".")
                    facts.append(
                        _fact(
                            "doc_model_mention",
                            f,
                            lineno,
                            line,
                            {"model": value, "provider": provider},
                        )
                    )
            for engine, pat in ENGINE_PATTERNS.items():
                if pat.search(line):
                    facts.append(_fact("doc_engine_mention", f, lineno, line, {"engine": engine}))
            m = RAG_PATTERN.search(line)
            if m:
                facts.append(_fact("doc_rag_mention", f, lineno, line, {"term": m.group(1)}))
        title = next(
            (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("# ")), None
        )
        if title and PurePosixPath(f.path).name.lower().startswith("readme"):
            facts.append(_fact("doc_title", f, 1, title, {"title": title}))
    return facts


def _fact(kind: str, f, lineno: int, line: str, data: dict) -> Fact:
    return Fact(
        kind=kind,
        key=f"doc:{f.path}",
        data={**data, "path": f.path},
        locator=Locator(path=f.path, line_start=lineno, line_end=lineno),
        excerpt=redact(line.strip())[:300],
        extractor=f"{EXTRACTOR}.{kind}",
        source="readme",
    )
