"""Published model records must not turn missing/contradictory evidence into success."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def review(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "model_review", ROOT / "scripts/render_model_validation.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    setattr(module, "DIR", tmp_path)
    record = json.loads(
        (ROOT / "docs/product/verification/real-model-qwen-nvidia.json").read_text()
    )
    path = tmp_path / "real-model-test.json"
    return module, record, path


@pytest.mark.parametrize("fault", ["false_check", "count", "nonfinite", "aborted"])
def test_contradictory_or_nonfinite_records_are_refused(review, fault):
    module, record, path = review
    if fault == "false_check":
        record["steps"]["select"]["checks"]["selection saved"] = False
    elif fault == "count":
        record["steps"]["evaluation_1"]["passed"] += 1
    elif fault == "aborted":
        record["completed"] = False
    else:
        record["steps"]["start"]["seconds"] = float("nan")
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        module.load()


def test_failed_record_and_unfavorable_quality_are_retained(review):
    module, record, path = review
    record["result"] = "failed"
    record["steps"]["select"]["checks"]["selection saved"] = False
    path.write_text(json.dumps(record))
    loaded = module.load()[0][1]
    assert loaded["result"] == "failed"
    assert loaded["steps"]["evaluation_1"]["failed"] > 0


def test_check_refuses_stale_report_without_overwriting(review, monkeypatch):
    module, record, path = review
    path.write_text(json.dumps(record))
    report = path.parent / "report.md"
    report.write_text("stale evidence")
    monkeypatch.setattr(module, "OUT", report)
    monkeypatch.setattr(sys, "argv", ["render_model_validation.py", "--check"])
    with pytest.raises(SystemExit, match="stale"):
        module.main()
    assert report.read_text() == "stale evidence"


def test_records_only_preserves_separate_historical_report(review, monkeypatch, capsys):
    module, record, path = review
    path.write_text(json.dumps(record))
    report = path.parent / "historical.md"
    report.write_text("historical report")
    monkeypatch.setattr(module, "OUT", report)
    monkeypatch.setattr(
        sys, "argv", ["render_model_validation.py", "--records-only", str(path.parent)]
    )
    module.main()
    assert "1 model records are consistent" in capsys.readouterr().out
    assert report.read_text() == "historical report"
