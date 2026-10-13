"""F2 (agent-actions-py), the second Python fixture: Scan reconstructs its agent and tools,
and Guard selects the approval-gate check for R4 (the refund confirmation deleted)."""

import sys
from pathlib import Path

import pytest

SCEN = Path(__file__).resolve().parents[3] / "fixtures" / "scenarios"
sys.path.insert(0, str(SCEN))

from f2_scenarios import F2, by_name, materialize  # noqa: E402
from f2_suite import F2_SUITE  # noqa: E402
from furnace.guardian.impact import analyze_impact, analyze_tree  # noqa: E402
from furnace.reconstruction.build import reconstruct  # noqa: E402


@pytest.fixture(scope="module")
def spec():
    return reconstruct(F2).appspec


def test_scan_finds_the_agent_call_and_its_tools(spec):
    assert any(c.key.split(":", 1)[1].startswith("app/agent.py::run_agent") for c in spec.llm_calls)
    tools = {t.name: t for t in spec.tools}
    assert tools["issue_refund"].approval_gate.value is True
    assert tools["send_email"].approval_gate.value is False
    assert tools["send_email"].side_effect.value.value in ("external", "write")


def test_approval_boundary_rule_still_runs_but_is_kept_out_of_the_actionable_blueprint():
    from furnace.blueprint.rules import EXPERIMENTAL, actionable, run_rules

    recs = run_rules(reconstruct(F2))
    fired = [r for r in recs if r.rule_id == "sec.tool_approval_boundary"]
    assert any("send_email" in r.title for r in fired)  # still computed and stored
    assert "sec.tool_approval_boundary" in EXPERIMENTAL
    assert not [r for r in actionable(recs) if r.rule_id in EXPERIMENTAL]
    assert len(actionable(recs)) == len(recs) - len(fired)


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    return analyze_tree(materialize(None, tmp_path_factory.mktemp("f2") / "base"))


def _selected(base, tmp_path, name):
    head = analyze_tree(materialize(by_name(name), tmp_path / name))
    return {s.key for s in analyze_impact(base, head, F2_SUITE).impact.selected}


def test_r4_selects_the_approval_gate_check(base, tmp_path):
    assert "security:approval_gate" in _selected(base, tmp_path, "f2_r4_refund_approval_removed")


def test_docs_only_runs_only_the_always_on_check(base, tmp_path):
    assert _selected(base, tmp_path, "f2_docs_only") == {"security:approval_gate"}


def test_without_a_prompt_harness_prompt_items_error_and_the_rest_still_run(tmp_path):
    """F2's agent loop has control flow before the messages are built, so no harness can be
    generated. That used to raise and skip every check; now only prompt-rendering items stop,
    with the reason, and never as a pass."""
    import shutil

    from furnace.guardian.execute import NO_HARNESS_FILE, GuardContext, prepare, run_items
    from furnace.guardian.impact import SuiteItem

    work, base, head = prepare(materialize(None, tmp_path / "a"), materialize(None, tmp_path / "b"))
    try:
        assert (base / NO_HARNESS_FILE).exists()
        ctx = GuardContext(base=base, head=head, questions=[], target=None)
        items = [
            SuiteItem("check:prompt_prefix_stable", "check", [], set()),
            SuiteItem("x", "nothing", [], set()),
        ]
        r = {x.key: x for x in run_items(items, ctx)}
        assert r["check:prompt_prefix_stable"].verdict == "error"
        assert "no prompt harness" in r["check:prompt_prefix_stable"].detail
        assert r["x"].verdict == "skip"
    finally:
        shutil.rmtree(work, ignore_errors=True)
