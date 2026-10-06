"""Guard executor dispatch, verdict logic and check-run rendering (no Docker, no GPU).

The executors that need a sandbox or an endpoint were verified live
(bench/results/2026-10-04-guard); here we pin the decision logic around them.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from furnace.contracts.guard import ChangedFile, Hunk, PRImpact, Selection, TouchedNode, TouchVia
from furnace.guardian import execute
from furnace.guardian.execute import GuardContext, ItemResult, run_items, selected_items
from furnace.guardian.impact import ImpactResult, SuiteItem
from furnace.guardian.report import check_run, repair_pr_body
from furnace_bench.schema import BenchTarget


def ctx(tmp_path: Path, target: BenchTarget | None = None, **kw) -> GuardContext:
    return GuardContext(
        base=tmp_path / "base", head=tmp_path / "head", questions=["q"], target=target, **kw
    )


TARGET = BenchTarget(base_url="http://localhost:1/v1", model="lab")


def item(key: str, kind: str) -> SuiteItem:
    return SuiteItem(key, kind, [], set())


# ---------------------------------------------------------------------- dispatch


def test_run_items_dispatches_and_never_passes_by_default(tmp_path, monkeypatch):
    def boom(_item, _ctx):
        raise RuntimeError("sandbox died")

    monkeypatch.setitem(execute.EXECUTORS, "unit", boom)
    seen: list[str] = []
    results = run_items(
        [item("unit:x", "unit"), item("weird:y", "weird"), item("check:nope", "check")],
        ctx(tmp_path),
        progress=seen.append,
    )
    assert [r.verdict for r in results] == ["error", "skip", "skip"]
    assert "RuntimeError: sandbox died" in results[0].detail
    assert results[1].detail == "no executor for weird"
    assert len(seen) == 3 and all(r.seconds >= 0 for r in results)


@pytest.mark.parametrize(
    ("key", "kind"),
    [
        ("check:citation_required", "check"),
        ("check:context_budget", "check"),
        ("bench:chat_perf_gate", "benchmark"),
        ("judge:ungrounded_answer", "judge"),
    ],
)
def test_items_without_an_endpoint_or_key_are_skipped(tmp_path, key, kind):
    (r,) = run_items([item(key, kind)], ctx(tmp_path))
    assert r.verdict == "skip"


def test_context_budget_needs_a_budget_even_with_an_endpoint(tmp_path):
    (r,) = run_items([item("check:context_budget", "check")], ctx(tmp_path, TARGET))
    assert r.verdict == "skip"


def test_unit_test_missing_on_head_is_skipped(tmp_path):
    (tmp_path / "head").mkdir()
    (r,) = run_items([item("unit:tests/test_gone.py", "unit")], ctx(tmp_path))
    assert r.verdict == "skip" and "does not exist" in r.detail


# ---------------------------------------------------------------------- citation verdicts


@pytest.mark.parametrize(
    ("base", "head", "expected"),
    [
        ((30, 34), (5, 34), "fail"),  # large, significant drop
        ((5, 34), (2, 34), "warn"),  # R3 on F1: 15% -> 6%, Fisher p=0.21
        ((10, 34), (9, 34), "pass"),  # within the 5-point budget
        ((10, 34), (14, 34), "pass"),  # improvement
    ],
)
def test_citation_verdict(tmp_path, monkeypatch, base, head, expected):
    calls: list[Path] = []

    def fake(root, _ctx):
        calls.append(root)
        p, n = base if root.name == "base" else head
        return p, n, ["bad answer"] * (n - p), "full answer path"

    monkeypatch.setattr(execute, "_app_answers", fake)
    c = ctx(tmp_path, TARGET)
    (r,) = run_items([item("check:citation_required", "check")], c)
    assert r.verdict == expected
    assert r.metrics["base_pass"] == base[0] and r.metrics["head_pass"] == head[0]
    assert len(r.metrics["examples"]) <= 3
    # The base revision is answered once per Guard run, then cached.
    run_items([item("check:citation_required", "check")], c)
    assert [p.name for p in calls] == ["base", "head", "head"]


def test_score_requires_retrieved_citations_or_documented_refusal():
    rows = [
        {"answer": "Pair it [doc:pairing].", "retrieved": ["pairing"]},
        {"answer": "Pair it [doc:invented].", "retrieved": ["pairing"]},
        {"answer": "I could not find that in the documentation.", "retrieved": []},
        {"answer": "Just do it.", "retrieved": ["pairing"]},
    ]
    passes, n, fails = execute._score(rows)
    assert (passes, n) == (2, 4)
    assert fails == ["Pair it [doc:invented].", "Just do it."]


def test_selected_items_preserves_suite_order():
    suite = [item("a", "unit"), item("b", "check"), item("c", "judge")]
    imp = ImpactResult(
        PRImpact(
            pr_number=1,
            base_sha="b",
            head_sha="h",
            selected=[
                Selection(key="c", kind="x", reason=""),
                Selection(key="a", kind="x", reason=""),
            ],
        ),
        set(),
        {},
    )
    assert [i.key for i in selected_items(imp, suite)] == ["a", "c"]


# ---------------------------------------------------------------------- check-run report


def _impact(**kw) -> ImpactResult:
    return ImpactResult(
        PRImpact(
            pr_number=7,
            base_sha="b",
            head_sha="h",
            changed=[
                ChangedFile(
                    path="app/prompts.py",
                    status="modified",
                    hunks=[Hunk(old_start=10, old_lines=1, new_start=10, new_lines=4)],
                )
            ],
            touched=[
                TouchedNode(
                    node_key="prompt:app/prompts.py::build_messages#system",
                    via=TouchVia.prompt_segment,
                    attr_changes={"static_prefix_chars": (849, 0)},
                )
            ],
            selected=[
                Selection(key="check:prompt_prefix_stable", kind="check", reason="prompt"),
                Selection(key="security:approval_gate", kind="check", reason="always"),
            ],
            skipped=[Selection(key="judge:ungrounded_answer", kind="evaluator", reason="no path")],
            full_suite_size=8,
            **kw,
        ),
        {"prompt"},
        {},
    )


def test_check_run_failure_has_title_groups_and_annotation():
    results = [
        ItemResult("check:prompt_prefix_stable", "fail", "requests share 0 leading characters"),
        ItemResult("security:approval_gate", "pass", "1 passed"),
    ]
    out = check_run(_impact(), results, "failure")
    assert out["conclusion"] == "failure"
    assert out["title"] == "1 regression found: prompt_prefix_stable"
    assert "**Ran 2 of 8 suite items**" in out["summary"]
    assert out["summary"].index("### Performance") < out["summary"].index("### Security")
    assert "`judge:ungrounded_answer`: no path" in out["summary"]
    assert "`static_prefix_chars` 849 -> 0" in out["text"]
    (ann,) = out["annotations"]
    assert (ann["path"], ann["start_line"], ann["end_line"]) == ("app/prompts.py", 10, 13)


def test_check_run_success_and_full_suite_fallback():
    out = check_run(
        _impact(fell_back_to_full=True), [ItemResult("unit:t", "pass", "ok")], "success"
    )
    assert out["title"] == "No regressions in 1 targeted check"
    assert "(full suite: unmapped change)" in out["summary"]
    assert out["annotations"] == []


def test_repair_pr_body_reports_both_revisions():
    attempt = SimpleNamespace(
        failure_mode_key="failure_mode:prefix_cache_miss",
        repro=SimpleNamespace(head_fails=True, base_passes=True),
        candidates=[
            SimpleNamespace(results={"regression_test": "1 passed", "existing_tests": "6 passed"})
        ],
    )
    perf = {
        "head_vs_base": {
            "baseline": 579,
            "value": 1473,
            "change_pct": 154.4,
            "verdict": "block",
            "prefix_hit_rate": (0.85, 0.0),
        },
        "candidate_vs_base": {
            "baseline": 579,
            "value": 648,
            "change_pct": 11.8,
            "verdict": "warn",
            "prefix_hit_rate": (0.85, 0.808),
        },
    }
    body = repair_pr_body(attempt, perf, "Moved the request id after the system prompt.", "t.py")
    assert "| PR head | 579 ms | 1473 ms | +154.4 % | 0% | block |" in body
    assert "| This repair | 579 ms | 648 ms | +11.8 % | 81% | warn |" in body
    assert "fails on the PR head: **True**" in body
    assert "Furnace never merges" in body
    assert "_No performance run attached._" in repair_pr_body(attempt, {}, "x", "t.py")
