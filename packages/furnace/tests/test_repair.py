"""Harness generation, the prefix-stability repair strategy, and the repair loop."""

import ast
import json
import shutil
import sys
from pathlib import Path

import pytest

SCEN = Path(__file__).resolve().parents[3] / "fixtures" / "scenarios"
sys.path.insert(0, str(SCEN))

from f1_scenarios import by_name, materialize  # noqa: E402
from f1_suite import F1_SUITE  # noqa: E402
from furnace.contracts.guard import RepairStatus  # noqa: E402
from furnace.forge.harness import HarnessError, generate_harness  # noqa: E402
from furnace.guardian.impact import analyze_impact, analyze_tree  # noqa: E402
from furnace.guardian.repair.strategies import (  # noqa: E402
    StrategyError,
    move_dynamic_to_log,
    move_dynamic_to_suffix,
)
from furnace.reconstruction.build import reconstruct  # noqa: E402

F1 = SCEN.parent / "apps" / "support-rag-py"


def test_harness_slices_the_chat_handler(tmp_path):
    root = materialize(None, tmp_path / "f1")
    h = generate_harness(reconstruct(root))
    assert (
        h.handler == "app/main.py::chat"
        and h.request_param == "req"
        and h.question_field == "question"
    )
    assert "from app.main import build_messages, rag_config, retrieve" in h.source
    assert "return messages" in h.source
    assert "StreamingResponse" not in h.source  # stops at the builder; never calls the model


def test_harness_refuses_handlers_it_cannot_slice(tmp_path):
    root = materialize(None, tmp_path / "f1")
    main = root / "app" / "main.py"
    src = main.read_text(encoding="utf-8").replace(
        "    cfg = rag_config()\n",
        "    if not req.question:\n        raise HTTPException(400)\n    cfg = rag_config()\n",
    )
    main.write_text(src, encoding="utf-8")
    with pytest.raises(HarnessError, match="control flow"):
        generate_harness(reconstruct(root))


def test_move_dynamic_to_suffix_on_r1(tmp_path):
    head = materialize(by_name("r1_dynamic_head"), tmp_path / "head")
    src = (head / "app" / "prompts.py").read_text(encoding="utf-8")
    edit = move_dynamic_to_suffix("app/prompts.py", src, "build_messages")
    # the system message is fully static; the per-request value ends the user message
    assert '"content": SYSTEM_PROMPT,' in edit.after
    assert (
        '"content": (f"CONTEXT:\\n{context}\\n\\nQUESTION: {question}") + "\\n\\n" + '
        'f"Request {uuid.uuid4().hex[:8]}'
    ) in edit.after
    assert "end of the last user message" in edit.explanation
    # only the two content expressions changed
    changed = [
        (a, b) for a, b in zip(src.splitlines(), edit.after.splitlines(), strict=True) if a != b
    ]
    assert len(changed) == 2
    # the repaired file is prefix-stable again according to the extractor
    (head / "app" / "prompts.py").write_text(edit.after, encoding="utf-8")
    (sysmsg,) = [p for p in reconstruct(head).appspec.prompts if p.key.endswith("#system")]
    assert sysmsg.dynamic_head is False


def test_move_dynamic_to_log_restores_the_base_prompt_exactly(tmp_path):
    base = materialize(None, tmp_path / "base")
    head = materialize(by_name("r1_dynamic_head"), tmp_path / "head")
    src = (head / "app" / "prompts.py").read_text(encoding="utf-8")
    edit = move_dynamic_to_log("app/prompts.py", src, "build_messages")
    # the per-request value is logged right before the messages are built, not sent
    assert "import logging\nimport uuid" in edit.after
    assert 'logging.getLogger(__name__).info(\n        "per-request values' in edit.after
    assert 'f"Request {uuid.uuid4().hex[:8]}' in edit.after.split("return [")[0]
    assert "model no longer sees" in edit.explanation
    # the messages it builds are the base revision's (same expression, formatting aside)
    (head / "app" / "prompts.py").write_text(edit.after, encoding="utf-8")
    base_src = (base / "app" / "prompts.py").read_text(encoding="utf-8")

    def returned(src: str) -> str:
        fn = next(
            n
            for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.FunctionDef) and n.name == "build_messages"
        )
        return ast.dump(next(n for n in fn.body if isinstance(n, ast.Return)))

    assert returned(edit.after) == returned(base_src)
    (sysmsg,) = [p for p in reconstruct(head).appspec.prompts if p.key.endswith("#system")]
    assert sysmsg.dynamic_head is False


def test_strategy_refuses_when_prefix_is_already_stable(tmp_path):
    root = materialize(None, tmp_path / "f1")
    with pytest.raises(StrategyError):
        move_dynamic_to_suffix(
            "app/prompts.py",
            (root / "app" / "prompts.py").read_text(encoding="utf-8"),
            "build_messages",
        )


docker = pytest.mark.skipif(shutil.which("docker") is None, reason="docker not available")


@docker
def test_repair_loop_writes_failing_test_first_and_verifies(tmp_path):
    from furnace.guardian.repair.loop import repair_prefix_instability

    base = materialize(None, tmp_path / "base")
    head = materialize(by_name("r1_dynamic_head"), tmp_path / "head")
    impact = analyze_impact(analyze_tree(base), analyze_tree(head), F1_SUITE)
    facts = json.loads((F1 / "docs" / "facts.json").read_text(encoding="utf-8"))
    out = repair_prefix_instability(
        base, head, impact, questions=[f["question"] for f in facts[:4]], change_label="r1"
    )
    a = out.attempt
    assert a.repro is not None and a.repro.head_fails and a.repro.base_passes
    assert a.status == RepairStatus.verified
    files = {line[6:] for line in out.patch.splitlines() if line.startswith("+++ b/")}
    assert files == {"app/prompts.py", "furnace_harness.py", out.test_path}


@docker
def test_repair_loop_refuses_without_a_reproduced_failure(tmp_path):
    from furnace.guardian.repair.loop import repair_prefix_instability

    base = materialize(None, tmp_path / "base")
    head = materialize(by_name("prompt_wording"), tmp_path / "head")  # not a prefix regression
    impact = analyze_impact(analyze_tree(base), analyze_tree(head), F1_SUITE)
    out = repair_prefix_instability(
        base, head, impact, questions=["q1", "q2"], change_label="wording"
    )
    assert out.attempt.status == RepairStatus.rejected and not out.patch


@docker
def test_repair_loop_tries_the_next_strategy_when_the_perf_gate_rejects(tmp_path):
    from furnace.guardian.repair.loop import repair_prefix_instability

    base = materialize(None, tmp_path / "base")
    head = materialize(by_name("r1_dynamic_head"), tmp_path / "head")
    impact = analyze_impact(analyze_tree(base), analyze_tree(head), F1_SUITE)
    calls: list[str] = []

    def perf_check(b, h, cand):  # stub gate: the suffix variant is over budget, the log one is not
        src = (cand / "app" / "prompts.py").read_text(encoding="utf-8")
        logged = "logging.getLogger" in src
        calls.append("log" if logged else "suffix")
        return {"within_budget": logged, "summary": "ok" if logged else "+45% p95, block"}

    out = repair_prefix_instability(
        base, head, impact, questions=["q1", "q2", "q3"], change_label="r1", perf_check=perf_check
    )
    a = out.attempt
    assert calls == ["suffix", "log"]
    assert [c.verdict for c in a.candidates] == ["fail", "pass"]
    assert a.selected == 1 and a.status == RepairStatus.verified
    assert "logging.getLogger" in out.files["app/prompts.py"]
