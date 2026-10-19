"""Evidence corruption tests; test mutations never alter the recorded campaign."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "prefix_review", Path(__file__).with_name("review.py")
)
assert spec and spec.loader
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    source = Path(__file__).parent
    dest = tmp_path / "repo" / "experiments" / "prefix-cache"
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.log"))
    shutil.copyfile(source.parents[1] / "README.md", dest.parents[1] / "README.md")
    monkeypatch.setattr(review, "HERE", dest)
    return dest


def test_saved_campaign_passes_without_writing():
    path = Path(__file__).with_name("verification.json")
    before = path.read_bytes(), path.stat().st_mtime_ns
    result = review.audit(review.DEFAULT_CAMPAIGN)
    assert result["checks"]["verified_measured_requests"] == 720
    assert result["checks"]["cache_counters_recomputed"]
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize("bad", ["NaN", "inf", "-1"])
def test_invalid_prometheus_counter_rejected(bad):
    with pytest.raises(ValueError, match="invalid counter"):
        review.counter(f"cache {bad}", "cache")


def test_counter_uses_exact_name_and_all_series():
    assert (
        review.counter('cache{engine="0"} 3\ncache{engine="1"} 4\ncache_created 99', "cache") == 7
    )


def test_missing_counter_is_unknown_not_zero():
    with pytest.raises(ValueError, match="missing"):
        review.counter("# HELP cache nothing\ncache_created 10", "cache")


def test_counter_reset_rejected():
    before = "vllm:prefix_cache_hits_total 8\nvllm:prefix_cache_queries_total 10"
    after = "vllm:prefix_cache_hits_total 1\nvllm:prefix_cache_queries_total 2"
    with pytest.raises(ValueError, match="reset"):
        review.cache_from_snapshots(before, after)


def first_run(root):
    return root / "runs" / review.DEFAULT_CAMPAIGN / "r1-A-attempt1"


def test_modified_raw_latency_rejected(evidence):
    path = next((first_run(evidence) / "measured").glob("*/requests.jsonl"))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["ttft_ms"] += 100
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="percentile"):
        review.audit(review.DEFAULT_CAMPAIGN)


def test_modified_cache_snapshot_rejected(evidence):
    path = first_run(evidence) / "metrics-after.prom"
    text = path.read_text(encoding="utf-8")
    import re

    text = re.sub(r"(vllm:prefix_cache_hits_total\{[^\n]*\}) [^\n]+", r"\g<1> 1", text)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=r"reset|disagrees"):
        review.audit(review.DEFAULT_CAMPAIGN)


def test_published_number_change_rejected(evidence):
    path = evidence / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["D"]["p50"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="published D p50"):
        review.audit(review.DEFAULT_CAMPAIGN)


def test_readme_table_drift_rejected(evidence):
    path = evidence.parents[1] / "README.md"
    path.write_text(path.read_text(encoding="utf-8").replace("43.27", "1.00"), encoding="utf-8")
    with pytest.raises(ValueError, match="table out of sync"):
        review.audit(review.DEFAULT_CAMPAIGN)


def test_wrong_cache_toggle_rejected(evidence):
    path = next((first_run(evidence) / "measured").glob("*/report.json"))
    report = json.loads(path.read_text(encoding="utf-8"))
    report["target"]["server_flags"]["cache"] = False
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="cache toggle"):
        review.audit(review.DEFAULT_CAMPAIGN)


def test_report_escapes_labels_and_needs_no_external_assets():
    result = review.audit(review.DEFAULT_CAMPAIGN)
    result["labels"]["A"] = '<script>alert("bad")</script>'
    page = review.document(result)
    assert "<script" not in page
    assert "&lt;script&gt;" in page
    assert 'src="http' not in page
    assert "3072.90" in page
    assert "r1-C-attempt1" in page


@pytest.mark.parametrize("campaign", ["..", "../elsewhere", "."])
def test_campaign_path_rejected(campaign):
    with pytest.raises(ValueError, match="directory name"):
        review.audit(campaign)
