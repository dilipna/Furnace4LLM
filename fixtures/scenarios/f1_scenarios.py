"""PR scenarios for fixture F1 (support-rag-py), used by Guard tests and FurnaceBench RQ3/RQ5.

Each scenario is a list of exact (path, old, new) edits applied to a copy of the
fixture, so every "PR" is readable and reproducible. `expected_categories` is
the author's statement of what kind of change it is (checked by tests);
regression ground truth for RQ3 comes from running the *full* suite, not from here.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

F1 = Path(__file__).resolve().parents[1] / "apps" / "support-rag-py"


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    edits: list[tuple[str, str, str]]
    expected_categories: set[str] = field(default_factory=set)


SCENARIOS: list[Scenario] = [
    Scenario(
        "docs_only",
        "README wording change",
        [("README.md", "Customer-support chatbot for Kilnworks", "Customer support assistant for Kilnworks")],
        {"docs"},
    ),
    Scenario(
        "prompt_wording",
        "Tone instruction reworded in the system prompt",
        [("app/prompts.py", "Be calm, precise and respectful.", "Be calm, precise, friendly and respectful.")],
        {"prompt"},
    ),
    Scenario(
        "r1_dynamic_head",
        "R1: request id and timestamp prepended to the system prompt 'for debugging'",
        [
            ("app/prompts.py", "from app.retriever import Chunk\n", "import uuid\nfrom datetime import UTC, datetime\n\nfrom app.retriever import Chunk\n"),
            (
                "app/prompts.py",
                '        {"role": "system", "content": SYSTEM_PROMPT},',
                '        {\n            "role": "system",\n            "content": f"Request {uuid.uuid4().hex[:8]} at {datetime.now(UTC).isoformat()}\\n" + SYSTEM_PROMPT,\n        },',
            ),
        ],
        {"prompt"},
    ),
    Scenario(
        "r2_context_bloat",
        "R2: retrieve 12 chunks and quadruple the context budget 'to improve recall'",
        [("config/rag.yaml", "top_k: 3\n  max_context_chars: 6000", "top_k: 12\n  max_context_chars: 24000")],
        {"retrieval_config"},
    ),
    Scenario(
        "r3_citation_strip",
        "R3: prompt told to drop citation tags 'because the UI shows sources separately'",
        [
            (
                "app/prompts.py",
                "After each sentence that uses the context, add the citation tag of the excerpt it came from, for example [doc:pairing]. Use the exact tag; never invent a tag that is not in the context.",
                "Do not include citation tags such as [doc:...] in your answer; the interface shows the sources separately.",
            ),
        ],
        {"prompt"},
    ),
    Scenario(
        "r3b_chunk_regex_strip",
        "Per-chunk regex meant to strip citation tags from the stream (ineffective: tags span chunks)",
        [
            ("app/llm.py", "import time\n", "import re\nimport time\n"),
            ("app/llm.py", "            yield chunk.choices[0].delta.content\n", '            yield re.sub(r"\\[doc:[^\\]]*\\]", "", chunk.choices[0].delta.content)\n'),
        ],
        {"code"},
    ),
    Scenario(
        "r4_approval_removed",
        "R4: approval check removed from ticket creation",
        [("app/tickets.py", "    if not approved:\n        raise ApprovalRequired(\"ticket creation requires user confirmation\")\n", "")],
        {"tool"},
    ),
    Scenario(
        "r5_prefix_caching_off",
        "R5: prefix caching disabled in the serving config",
        [("docker-compose.yml", "      - --enable-prefix-caching", "      - --no-enable-prefix-caching")],
        {"serving_config"},
    ),
    Scenario(
        "max_tokens_up",
        "Generation budget raised from 256 to 1024 tokens",
        [("config/rag.yaml", "max_tokens: 256", "max_tokens: 1024")],
        {"generation_config"},
    ),
    Scenario(
        "model_swap",
        "Serving model changed to the 1.5B AWQ checkpoint",
        [("docker-compose.yml", "      - Qwen/Qwen2.5-0.5B-Instruct", "      - Qwen/Qwen2.5-1.5B-Instruct-AWQ")],
        {"model"},
    ),
    Scenario(
        "test_only",
        "New retriever unit test",
        [("tests/test_retriever.py", "def test_top_k_respected():", 'def test_pairing_question():\n    assert retrieve("pair controller", top_k=1)[0].doc_id == "pairing"\n\n\ndef test_top_k_respected():')],
        {"tests"},
    ),
    Scenario(
        "dependency_bump",
        "Pin a newer FastAPI",
        [("requirements.txt", "fastapi>=0.115", "fastapi>=0.118")],
        set(),
    ),
    Scenario(
        "health_payload",
        "Health endpoint returns a version field",
        [("app/main.py", '    return {"ok": True}', '    return {"ok": True, "version": "1.1"}')],
        {"code_off_llm_path"},
    ),
]


def materialize(scenario: Scenario | None, dest: Path) -> Path:
    """Copy F1 to `dest` (excluding runtime dirs) and apply the scenario's edits."""
    shutil.copytree(F1, dest, ignore=shutil.ignore_patterns(".venv", "traces", "__pycache__", ".pytest_cache"))
    if scenario is None:
        return dest
    for path, old, new in scenario.edits:
        p = dest / path
        text = p.read_text(encoding="utf-8")
        if old not in text:
            raise ValueError(f"scenario {scenario.name}: {old!r} not found in {path}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return dest


def by_name(name: str) -> Scenario:
    return next(s for s in SCENARIOS if s.name == name)
