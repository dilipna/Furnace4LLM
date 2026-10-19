"""Offline protocol invariants; these tests are not inference measurements."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "prefix_experiment", Path(__file__).with_name("benchmark.py")
)
assert spec and spec.loader
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)

render_spec = importlib.util.spec_from_file_location(
    "prefix_render", Path(__file__).with_name("render.py")
)
assert render_spec and render_spec.loader
renderer = importlib.util.module_from_spec(render_spec)
render_spec.loader.exec_module(renderer)


def test_exactly_sixty_distinct_short_queries():
    qs = experiment.queries()
    assert len(qs) == len(set(qs)) == 60
    assert all(len(q.split()) < 30 for q in qs)


def test_paired_workload_and_metadata_placement():
    prefix = "stable runbook text"
    metadata = [f"session={i}" for i in range(60)]
    rows = {c: experiment.payloads(c, prefix, experiment.queries(), metadata) for c in "ABCD"}
    assert rows["A"] == rows["B"]
    for i in range(60):
        assert len({rows[c][i]["messages"][1]["content"] for c in "ABCD"}) == 1
        assert rows["C"][i]["messages"][0]["content"] == metadata[i] + "\n\n" + prefix
        assert rows["D"][i]["messages"][0]["content"] == prefix + "\n\n" + metadata[i]
        assert all(rows[c][i]["max_tokens"] == 32 for c in "ABCD")


def test_partial_and_failed_runs_cannot_pass_completion_check():
    with pytest.raises(RuntimeError, match="59/60"):
        experiment.require_complete(SimpleNamespace(records=[SimpleNamespace(ok=True)] * 59), 60)
    with pytest.raises(RuntimeError, match="59/60"):
        experiment.require_complete(
            SimpleNamespace(records=[SimpleNamespace(ok=True)] * 59 + [SimpleNamespace(ok=False)]),
            60,
        )


def test_cache_rate_uses_counter_differences():
    before = {"vllm:prefix_cache_hits_total": 200, "vllm:prefix_cache_queries_total": 300}
    after = {"vllm:prefix_cache_hits_total": 290, "vllm:prefix_cache_queries_total": 400}
    assert experiment.cache_delta(before, after) == {"hits": 90, "queries": 100, "rate": 0.9}


def test_missing_cache_metrics_are_unknown_not_zero():
    assert experiment.cache_delta({}, {}) == {"hits": None, "queries": None, "rate": None}


def test_reset_cache_metrics_are_an_error():
    with pytest.raises(RuntimeError, match="reset"):
        experiment.cache_delta(
            {"vllm:prefix_cache_hits": 10, "vllm:prefix_cache_queries": 20},
            {"vllm:prefix_cache_hits": 0, "vllm:prefix_cache_queries": 0},
        )


def test_saved_logs_remove_machine_paths():
    assert str(experiment.ROOT) not in experiment.redact(str(experiment.ROOT) + "/file.py")
    assert "/root/" not in experiment.redact("loaded /root/.cache/model.bin")


def sample_summaries():
    """Test fixtures only; these never become experiment artifacts."""
    return [
        {
            "repeat": repeat,
            "condition": condition,
            "status": "success",
            "n_ok": 60,
            "ttft_p50_ms": 10.0,
            "ttft_p95_ms": 20.0,
            "output_tok_s": 30.0,
            "cache": {"hits": 9, "queries": 10, "rate": 0.9},
        }
        for repeat in (1, 2, 3)
        for condition in "ABCD"
    ]


def test_renderer_refuses_to_fill_missing_runs():
    with pytest.raises(ValueError, match="campaign incomplete"):
        renderer.summary(sample_summaries()[:-1])


def test_renderer_rejects_duplicate_successes():
    rows = sample_summaries()
    with pytest.raises(ValueError, match="multiple successful"):
        renderer.summary([*rows, rows[0]])


def test_renderer_excludes_failed_attempts():
    rows = sample_summaries()
    result = renderer.summary([{"status": "failed", "repeat": 1, "condition": "A"}, *rows])
    assert len(result["A"]["runs"]) == 3


def test_renderer_rejects_incomplete_success_record():
    rows = sample_summaries()
    rows[0]["n_ok"] = 59
    with pytest.raises(ValueError, match="incomplete requests"):
        renderer.summary(rows)
