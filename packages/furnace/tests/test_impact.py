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
    keys = {t.node_key for t in impacts["r3b_chunk_regex_strip"].impact.touched}
    # an import inserted above the LLM call must not look like "call site removed/added"
    assert not any(k.endswith("#llm1") for k in keys)
    assert all(
        t.attr_changes.get("exists") is None
        for t in impacts["r3b_chunk_regex_strip"].impact.touched
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


def test_lost_stable_prefix_is_exactly_the_false_to_true_head_change():
    from furnace.contracts.guard import TouchedNode, TouchVia
    from furnace.guardian.impact import lost_stable_prefix

    t = TouchedNode(
        node_key="prompt:src/api/chat.py::chat_handler#system",
        via=TouchVia.symbol,
        attr_changes={"dynamic_head": (False, True)},
    )
    assert lost_stable_prefix(t)
    assert not lost_stable_prefix(
        t.model_copy(update={"attr_changes": {"dynamic_head": (True, False)}})
    )
    assert not lost_stable_prefix(t.model_copy(update={"node_key": "prompt:x.py::SYSTEM_PROMPT"}))


def test_signature_selection_on_a_real_tree_without_workflows(tmp_path):
    """External apps where no traced workflow reaches the prompt (2026-10-11 set 4): the
    prefix-instability signature must still pull in the perf benchmark."""
    from furnace.guardian.impact import SuiteItem

    app = 'SYSTEM = "You are helpful."\n\n\ndef build(q):\n    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}]\n'
    (tmp_path / "base").mkdir()
    (tmp_path / "head").mkdir()
    (tmp_path / "base" / "prompts.py").write_text(app)
    (tmp_path / "head" / "prompts.py").write_text(
        "import uuid\n"
        + app.replace('"content": SYSTEM}', '"content": f"req {uuid.uuid4()} " + SYSTEM}')
    )
    suite = [
        SuiteItem("check:prompt_prefix_stable", "check", ["prompt:*"], {"prompt"}),
        SuiteItem("bench:perf_gate", "benchmark", ["workflow:*"], {"prompt", "model"}),
        SuiteItem("bench:unrelated", "benchmark", ["workflow:*"], {"serving_config"}),
    ]
    imp = analyze_impact(analyze_tree(tmp_path / "base"), analyze_tree(tmp_path / "head"), suite)
    sel = {s.key: s.reason for s in imp.impact.selected}
    assert "bench:perf_gate" in sel and "prefix-instability signature" in sel["bench:perf_gate"]
    assert "bench:unrelated" not in sel  # only benchmarks that detect prompt changes


# ---- uncertain or unsupported analysis must widen the selection, never silently narrow it


def _head_with(tmp_path, edits: dict[str, str | None]):
    """F1 with files written (str) or deleted (None), on top of an unchanged tree."""
    root = materialize(None, tmp_path / "h")
    for rel, text in edits.items():
        p = root / rel
        if text is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    return root


def _impact(base, root):
    return analyze_impact(base, analyze_tree(root), F1_SUITE).impact


def test_a_corpus_file_the_app_reads_falls_back(base, tmp_path):
    # app/retriever.py loads docs/*.md: an edited article changes what is retrieved and cited
    p = materialize(None, tmp_path / "x") / "docs" / "pairing.md"
    text = p.read_text(encoding="utf-8").replace("controller", "kiln controller", 1)
    imp = _impact(base, _head_with(tmp_path, {"docs/pairing.md": text}))
    assert imp.fell_back_to_full and "docs/pairing.md" in imp.selected[0].reason


def test_unsupported_language_source_falls_back(base, tmp_path):
    imp = _impact(base, _head_with(tmp_path, {"app/static/widget.ts": "export const x = 1;\n"}))
    assert imp.fell_back_to_full and "does not parse" in imp.selected[0].reason


def test_unmodelled_file_in_the_app_falls_back(base, tmp_path):
    imp = _impact(base, _head_with(tmp_path, {"app/data/thresholds.csv": "kiln,1280\n"}))
    assert imp.fell_back_to_full and "app/data/thresholds.csv" in imp.selected[0].reason


def test_a_template_the_scanner_models_is_targeted_not_a_fallback(base, tmp_path):
    imp = _impact(base, _head_with(tmp_path, {"app/templates/answer.j2": "{{ answer }}\n"}))
    assert not imp.fell_back_to_full


def test_added_module_that_maps_to_no_node_falls_back(base, tmp_path):
    imp = _impact(base, _head_with(tmp_path, {"app/flags.py": "FLAG = compute_flag()\n"}))
    assert imp.fell_back_to_full


def test_removed_module_that_maps_to_no_node_falls_back(base, tmp_path):
    src = materialize(None, tmp_path / "y")
    empty = [p for p in (src / "app").glob("*.py") if p.name == "__init__.py"]
    target = "app/__init__.py" if empty else None
    if target is None:
        pytest.skip("F1 has no app/__init__.py")
    imp = _impact(base, _head_with(tmp_path, {target: None}))
    assert imp.fell_back_to_full


def test_unparseable_python_falls_back(base, tmp_path):
    p = materialize(None, tmp_path / "z") / "app" / "main.py"
    broken = p.read_text(encoding="utf-8").replace("def ", "def (", 1)
    imp = _impact(base, _head_with(tmp_path, {"app/main.py": broken}))
    assert imp.fell_back_to_full and "does not parse" in imp.selected[0].reason


def test_inert_changes_do_not_fall_back(base, tmp_path):
    imp = _impact(
        base,
        _head_with(
            tmp_path,
            {
                ".github/workflows/ci.yml": "on: push\n",
                "docs/diagram.png": "not really a png\n",
                "CHANGELOG.md": "- wording\n",
            },
        ),
    )
    assert not imp.fell_back_to_full
