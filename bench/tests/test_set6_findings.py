"""The set-6 finding scorer decides what counts as a correct finding, so its matching is tested."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import set6_findings as sf


def P(rule, keys=(), locs=()):
    return {"rule": rule, "title": rule, "node_keys": list(keys), "locs": list(locs)}


def test_per_item_findings_match_by_name_or_by_line_and_only_once():
    item = {"file": "rag.py", "symbol": "_RAG_PROMPT", "line": 141}
    assert sf.item_matches(item, P("obs.prompt_versioning", ["prompt:rag.py::_RAG_PROMPT"]))
    assert sf.item_matches(item, P("obs.prompt_versioning", locs=[("rag.py", 140, 160)]))
    assert not sf.item_matches(item, P("obs.prompt_versioning", ["prompt:other.py::_RAG_PROMPT"]))
    assert not sf.item_matches(item, P("obs.prompt_versioning", locs=[("rag.py", 1, 20)]))
    gt = {
        "expected_findings": [
            {"rule": "obs.prompt_versioning", "item": item},
            {
                "rule": "obs.prompt_versioning",
                "item": {"file": "rag.py", "symbol": "_X", "line": 9},
            },
            {"rule": "rel.llm_timeout", "item": "app"},
        ]
    }
    preds = [
        P("obs.prompt_versioning", ["prompt:rag.py::_RAG_PROMPT"]),
        P("rel.llm_timeout"),
        P("rel.llm_timeout"),  # a second app-level finding of the same rule is unexpected
        P("eval.regression_suite"),
    ]
    r = sf.score_app(gt, preds)
    assert (r["expected"], r["emitted"], r["matched"]) == (3, 4, 2)
    assert [m["rule"] for m in r["missed"]] == ["obs.prompt_versioning"]
    assert sorted(u["rule"] for u in r["unexpected"]) == [
        "eval.regression_suite",
        "rel.llm_timeout",
    ]


def test_rules_an_app_did_not_label_are_left_out_of_both_sides():
    gt = {
        "not_labeled_findings": ["obs.prompt_versioning"],
        "expected_findings": [{"rule": "rel.llm_timeout", "item": "app"}],
    }
    r = sf.score_app(gt, [P("obs.prompt_versioning", ["prompt:a.py::X"]), P("rel.llm_timeout")])
    assert (r["expected"], r["emitted"], r["matched"]) == (1, 1, 1)
    assert r["excluded_emitted"] == ["obs.prompt_versioning"]
