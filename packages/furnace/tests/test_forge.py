"""Forge retrofit planning and validation on fixture F1."""

import json
import shutil
import sys
from pathlib import Path

import pytest

SCEN = Path(__file__).resolve().parents[3] / "fixtures" / "scenarios"
sys.path.insert(0, str(SCEN))

from f1_scenarios import materialize  # noqa: E402
from furnace.blueprint.rules import run_rules  # noqa: E402
from furnace.contracts.guard import ChangeType  # noqa: E402
from furnace.forge.planner import Planner, apply  # noqa: E402
from furnace.reconstruction.build import reconstruct  # noqa: E402

F1 = SCEN.parent / "apps" / "support-rag-py"
QUESTIONS = [
    f["question"] for f in json.loads((F1 / "docs" / "facts.json").read_text(encoding="utf-8"))
]
WORKLOAD = {
    "name": "f1",
    "source": "traces",
    "synthetic": False,
    "n_observed": 89,
    "slo": {"ttft_p95_ms": 500},
}


@pytest.fixture(scope="module")
def plan(tmp_path_factory):
    root = materialize(None, tmp_path_factory.mktemp("f1") / "repo")
    rec = reconstruct(root)
    result = Planner(rec, run_rules(rec), questions=QUESTIONS, workload=WORKLOAD).run(
        shared_prefix=3954
    )
    return root, result


def test_every_change_states_reason_target_and_risk(plan):
    _, result = plan
    assert result.plan.changes
    for c in result.plan.changes:
        assert c.reason and c.target and c.risk, c.path


def test_only_fired_recommendations_produce_artifacts(plan):
    _, result = plan
    paths = set(result.files)
    assert "tests/furnace/test_create_ticket_approval.py" in paths  # approval gate exists in F1
    assert "tests/furnace/test_llm_timeout.py" in paths  # F1 has no timeout
    assert "benchmarks/workloads.yaml" in paths
    codemods = {c.path for c in result.plan.changes if c.change_type == ChangeType.codemod}
    assert codemods == {"app/llm.py", "app/prompts.py"}


def test_timeout_codemod_changes_only_the_client_call(plan):
    root, result = plan
    before = (root / "app" / "llm.py").read_text(encoding="utf-8").splitlines()
    after = result.files["app/llm.py"].splitlines()
    changed = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert len(changed) == 1 and "timeout=60.0" in changed[0][1]


def test_prompt_extraction_keeps_exact_text_and_is_still_prefix_stable(plan, tmp_path):
    root, result = plan
    forged = Path(shutil.copytree(root, tmp_path / "forged"))
    apply(result, forged)
    md = (forged / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
    body = md.split("---\n", 2)[2]
    import ast

    src = (root / "app" / "prompts.py").read_text(encoding="utf-8")
    original = next(
        n.value.value
        for n in ast.parse(src).body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "SYSTEM_PROMPT"
        and isinstance(n.value, ast.Constant)
    )
    assert body == original
    rec = reconstruct(forged)
    (sysmsg,) = [p for p in rec.appspec.prompts if p.key.endswith("#system")]
    assert sysmsg.dynamic_head is False and sysmsg.static_chars == len(original)
    # the citation instruction is still visible to the rules through the prompt file
    assert "eval.citation_contract" in {r.rule_id for r in run_rules(rec, include_resolved=True)}


def test_resolved_findings_require_their_verifying_artifact(plan, tmp_path):
    root, result = plan
    forged = Path(shutil.copytree(root, tmp_path / "forged"))
    apply(result, forged)
    after = {r.rule_id for r in run_rules(reconstruct(forged))}
    assert "sec.approval_gate_regression_test" not in after
    assert "obs.genai_tracing" in after  # Forge does not instrument tracing yet: must remain
    (forged / "tests" / "furnace" / "test_create_ticket_approval.py").unlink()
    assert "sec.approval_gate_regression_test" in {
        r.rule_id for r in run_rules(reconstruct(forged))
    }


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not available")
def test_validation_in_sandbox(plan):
    from furnace.forge.validate import validate

    root, result = plan
    v = validate(root, result, QUESTIONS)
    assert v.prompts_identical and v.installed_tests == "pass" and v.existing_tests == "pass"
    assert "rel.llm_timeout" in v.resolved_findings
