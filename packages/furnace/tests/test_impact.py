"""Guard impact analysis on the F1 PR scenarios."""

import sys
from pathlib import Path

import pytest

SCEN = Path(__file__).resolve().parents[3] / "fixtures" / "scenarios"
sys.path.insert(0, str(SCEN))

from f1_scenarios import SCENARIOS, by_name, materialize  # noqa: E402
from f1_suite import F1_SUITE  # noqa: E402
from furnace.guardian.impact import analyze_impact, analyze_tree  # noqa: E402


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    return analyze_tree(materialize(None, tmp_path_factory.mktemp("f1") / "base"))


@pytest.fixture(scope="module")
def impacts(base, tmp_path_factory):
    root = tmp_path_factory.mktemp("heads")
    out = {}
    for s in SCENARIOS:
        out[s.name] = analyze_impact(base, analyze_tree(materialize(s, root / s.name)), F1_SUITE)
    return out


def selected(impacts, name):
    return {s.key for s in impacts[name].impact.selected}


# The check that actually detects each seeded regression must be selected.
@pytest.mark.parametrize(
    ("scenario", "must_run"),
    [
        ("r1_dynamic_head", {"check:prompt_prefix_stable", "bench:chat_perf_gate"}),
        (
            "r2_context_bloat",
            {"check:context_budget", "bench:chat_perf_gate", "check:citation_required"},
        ),
        ("r3_citation_strip", {"check:citation_required"}),
        ("r4_approval_removed", {"security:approval_gate"}),
        ("r5_prefix_caching_off", {"bench:chat_perf_gate"}),
    ],
)
def test_regression_detectors_are_selected(impacts, scenario, must_run):
    assert must_run <= selected(impacts, scenario)


@pytest.mark.parametrize(
    ("scenario", "must_skip"),
    [
        (
            "docs_only",
            {"bench:chat_perf_gate", "judge:ungrounded_answer", "check:citation_required"},
        ),
        ("health_payload", {"bench:chat_perf_gate", "judge:ungrounded_answer"}),
        ("r4_approval_removed", {"bench:chat_perf_gate", "judge:ungrounded_answer"}),
        (
            "r1_dynamic_head",
            {"unit:tests/test_retriever.py"},
        ),  # sibling of the prompt, not affected
    ],
)
def test_unaffected_items_are_skipped_with_reasons(impacts, scenario, must_skip):
    imp = impacts[scenario].impact
    skipped = {s.key: s.reason for s in imp.skipped}
    assert must_skip <= set(skipped)
    assert all(reason for reason in skipped.values())


def test_scenario_categories_match_author_intent(impacts):
    for s in SCENARIOS:
        assert s.expected_categories <= impacts[s.name].categories, s.name


def test_r1_records_the_semantic_attribute_change(impacts):
    t = {x.node_key: x for x in impacts["r1_dynamic_head"].impact.touched}
    sysmsg = t["prompt:app/prompts.py::build_messages#system"]
    assert sysmsg.attr_changes["dynamic_head"] == (False, True)
    assert sysmsg.attr_changes["static_prefix_chars"][1] < 50


def test_selection_carries_a_graph_path(impacts):
    imp = impacts["r2_context_bloat"].impact
    perf = next(s for s in imp.selected if s.key == "bench:chat_perf_gate")
    touched = {t.node_key for t in imp.touched}
    assert perf.path[0] in touched  # justification starts at something the PR changed
    assert perf.path[-1] == "workflow:app/main.py::POST /chat"


def test_line_shifts_do_not_create_spurious_node_changes(impacts):
    keys = {t.node_key for t in impacts["r3_citation_strip"].impact.touched}
    # an import inserted above the LLM call must not look like "call site removed/added"
    assert not any(k.endswith("#llm1") for k in keys)
    assert all(
        t.attr_changes.get("exists") is None
        for t in impacts["r3_citation_strip"].impact.touched
        if "#llm" in t.node_key
    )


def test_unmapped_app_code_falls_back_to_full_suite(base, tmp_path):
    head_root = materialize(by_name("docs_only"), tmp_path / "h")
    p = head_root / "app" / "config.py"
    p.write_text(
        p.read_text(encoding="utf-8") + "\nFEATURE_FLAG = compute_flag()\n", encoding="utf-8"
    )
    r = analyze_impact(base, analyze_tree(head_root), F1_SUITE)
    assert r.impact.fell_back_to_full
    assert len(r.impact.selected) == len(F1_SUITE)
    assert "maps to no graph node" in r.impact.selected[0].reason


def test_targeted_suite_is_smaller_than_full(impacts):
    total = sum(len(i.impact.selected) for i in impacts.values())
    assert total < len(F1_SUITE) * len(SCENARIOS) * 0.6
