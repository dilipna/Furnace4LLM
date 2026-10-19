"""Exercise the shipped Forge test, not a replacement implementation of its rule."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "guard_replay", Path(__file__).with_name("rehearse_guard.py")
)
assert spec and spec.loader
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def workload(prefixes):
    return [
        {
            "question": f"question {i}",
            "messages": [
                {"role": "system", "content": prefix},
                {"role": "user", "content": f"question {i}"},
            ],
        }
        for i, prefix in enumerate(prefixes)
    ]


def test_real_template_fails_regression_and_accepts_preserved_prefix():
    base = workload(["long shared runbook " * 20] * 3)
    broken = workload([f"unique {i} " + "long shared runbook " * 20 for i in range(3)])
    fixed = workload(["long shared runbook " * 20 + f" unique {i}" for i in range(3)])
    source = replay.template()
    assert "Installed by Furnace Forge" in source
    assert replay.compare(base, broken, source)["exit_code"] == 1
    assert replay.compare(base, fixed, source)["exit_code"] == 0


def test_unmatched_questions_are_an_error_not_a_pass():
    base = workload(["shared text " * 20] * 2)
    head = workload(["shared text " * 20] * 2)
    head[0]["question"] = "different"
    with pytest.raises(ValueError, match="identical questions"):
        replay.compare(base, head, replay.template())


def test_role_labels_alone_do_not_establish_a_useful_baseline():
    base = workload(["abc", "xyz"])
    with pytest.raises(ValueError, match="meaningful shared text"):
        replay.compare(base, base, replay.template())


def test_duplicate_questions_rejected(tmp_path):
    path = tmp_path / "workload.jsonl"
    row = {"messages": [{"role": "user", "content": "same question"}]}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        replay.load_workload(path)


def test_multimodal_input_refused_explicitly(tmp_path):
    path = tmp_path / "workload.jsonl"
    row = {"messages": [{"role": "user", "content": [{"type": "image"}]}]}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="text messages"):
        replay.load_workload(path)


@pytest.mark.parametrize("row", [[1, 2], {"messages": "wrong type"}])
def test_invalid_row_shape_is_a_clear_input_error(tmp_path, row):
    path = tmp_path / "workload.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="messages array"):
        replay.load_workload(path)


@pytest.mark.parametrize(("condition", "expected_exit"), [("C", 1), ("D", 0)])
def test_candidate_cli_uses_real_failure_exit_code(monkeypatch, condition, expected_exit):
    manifest = json.loads(
        (replay.HERE / "runs" / replay.CAMPAIGN / "manifest.json").read_text(encoding="utf-8")
    )
    selected = {
        row["condition"]: replay.HERE / row["path"] / "workload.jsonl"
        for row in manifest["attempts"]
        if row["repeat"] == 1 and row["status"] == "success"
    }
    monkeypatch.setattr(
        sys,
        "argv",
        ["rehearse_guard.py", "--base", str(selected["A"]), "--head", str(selected[condition])],
    )
    assert replay.main() == expected_exit


def test_recorded_workload_replay_matches_all_expected_outcomes():
    result = replay.rehearse()
    assert result["all_expected_outcomes"]
    assert len(result["results"]) == 12
    assert [r["status"] for r in result["results"] if r["condition"] == "C"] == ["FAIL"] * 3
    assert [r["status"] for r in result["results"] if r["condition"] == "B"] == ["PASS"] * 3
