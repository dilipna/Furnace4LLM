"""The FurnaceBench scorers decide every reported number, so they are tested like product code."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rq1
import rq3
import rq4
from furnace.contracts.appspec import AppSpec


def test_prf_and_empty_cases():
    assert rq1.prf(2, 4, 2) == {
        "tp": 2,
        "n_pred": 4,
        "n_truth": 2,
        "precision": 0.5,
        "recall": 1.0,
        "f1": pytest.approx(2 / 3),
    }
    assert rq1.prf(0, 0, 3)["recall"] == 0.0 and rq1.prf(0, 0, 3)["precision"] is None
    assert rq1.prf(0, 0, 0)["f1"] is None


def test_match_is_one_to_one():
    pairs, missed, extra = rq1.match(["a", "a", "b"], ["a", "c"], lambda t, p: t == p)
    assert pairs == [("a", "a")] and missed == ["a", "b"] and extra == ["c"]


def test_site_match_rules():
    t = {"file": "app.py", "function": "chain", "also_accept": ["handle"]}
    assert rq1._site_match(t, "component:app.py::chain#llm0")
    assert rq1._site_match(t, "component:app.py::handle#llm1")
    assert not rq1._site_match(t, "component:app.py::other#llm0")
    assert not rq1._site_match(t, "component:other.py::chain#llm0")
    assert rq1._site_match(
        {"file": "p.py", "function": "<module>"}, "component:p.py::<module>#llm0"
    )
    assert rq1._split_key("component:pages/1_File_Q&A.py::<module>#llm0") == (
        "pages/1_File_Q&A.py",
        "<module>",
    )


def test_model_ids_ignore_version_hash():
    h = "df7690f1994d94e96ad9d568eac121aecf50684a0b0963b25a41cc40061269e5"
    assert rq1._model(f"a16z-infra/llama13b-v2-chat:{h}") == "a16z-infra/llama13b-v2-chat"
    assert rq1._model("qwen2.5:7b") == "qwen2.5:7b"  # an Ollama tag is part of the id


def test_empty_appspec_scores_only_absent_facts():
    gt = {
        "llm_calls": [{"file": "a.py", "function": "f"}],
        "uses_rag": False,
        "existing_reliability": {"tests": False, "tracing": "none"},
    }
    sc = rq1.score(AppSpec(), gt)
    assert sc["categories"]["llm_call_sites"]["recall"] == 0.0
    assert all(
        a["correct"] for a in sc["attributes"]
    )  # absent facts are "correct" for an empty scan


def test_ece():
    pts = [(0.9, True, "x")] * 9 + [(0.9, False, "x")]
    e = rq1.ece(pts)
    assert e["ece"] == pytest.approx(0.0) and e["n"] == 10
    assert rq1.ece([(0.9, False, "x")])["ece"] == pytest.approx(0.9)


def test_rq3_recall_counts_misses_by_targeting():
    recs = [
        {
            "selected": ["a", "b"],
            "full_fail": ["a"],
            "missed_fail": [],
            "full_warn": ["c"],
            "missed_warn": ["c"],
            "full_seconds": 100,
            "targeted_seconds": 20,
            "full_endpoint_seconds": 80,
            "targeted_endpoint_seconds": 10,
            "judge_tokens_est": {"full": 10, "targeted": 0},
            "targeted_conclusion": "failure",
            "full_conclusion": "failure",
        },
        {
            "selected": [],
            "full_fail": ["d"],
            "missed_fail": ["d"],
            "full_warn": [],
            "missed_warn": [],
            "full_seconds": 50,
            "targeted_seconds": 1,
            "full_endpoint_seconds": 0,
            "targeted_endpoint_seconds": 0,
            "judge_tokens_est": {"full": 10, "targeted": 0},
            "targeted_conclusion": "success",
            "full_conclusion": "failure",
        },
    ]
    s = rq3.summarize(recs)
    assert s["regression_recall"] == {"caught": 1, "total": 2, "recall": 0.5}
    assert s["warn_recall"] == {"caught": 0, "total": 1}
    assert s["conclusion_agreement"] == 1
    assert s["items_executed_pct"] == pytest.approx(2 / (len(rq3.F1_SUITE) * 2) * 100)


def test_rq4_aggregate():
    assert rq4._agg([3.0, 1.0, 2.0, None]) == {"median": 2.0, "min": 1.0, "max": 3.0, "n": 3}  # type: ignore[list-item]
    assert rq4._agg([])["median"] is None


def test_gpu_drivers_refuse_battery(monkeypatch):
    import common

    monkeypatch.setattr(
        common,
        "power_state",
        lambda: {"on_ac": False, "battery_pct": 29, "gpu_enforced_power_limit_w": 25.0},
    )
    with pytest.raises(SystemExit, match="refusing to benchmark on battery"):
        common.require_ac_power()
    assert common.require_ac_power(allow_battery=True)["on_ac"] is False
    monkeypatch.setattr(
        common,
        "power_state",
        lambda: {"on_ac": True, "battery_pct": 80, "gpu_enforced_power_limit_w": 75.0},
    )
    assert common.require_ac_power()["on_ac"] is True
