import pytest

from furnace_bench.telemetry.collector import Sample, TelemetryCollector
from furnace_bench.telemetry.prom import parse_prometheus

PROM = """
# HELP vllm:num_requests_running Number of requests running
# TYPE vllm:num_requests_running gauge
vllm:num_requests_running{engine="0",model_name="lab"} 3.0
vllm:prefix_cache_queries_total{engine="0",model_name="lab"} 1000.0
vllm:prefix_cache_queries_created{engine="0",model_name="lab"} 1.79e+09
vllm:time_to_first_token_seconds_bucket{le="0.1"} 4.0
vllm:time_to_first_token_seconds_sum{engine="0"} 0.5
x{a="1"} 1
x{a="2"} 2
"""


def test_parse_prometheus_sums_labels_and_skips_buckets():
    m = parse_prometheus(PROM)
    assert m["vllm:num_requests_running"] == 3.0
    assert m["vllm:prefix_cache_queries_total"] == 1000.0
    assert "vllm:prefix_cache_queries_created" not in m
    assert "vllm:time_to_first_token_seconds_bucket" not in m
    assert m["x"] == 3.0


def test_aggregate_counter_deltas_and_gauges():
    c = TelemetryCollector(t0=0.0, scrape=None, nvml=None)
    c.samples = [
        Sample(0.0, {"prefix_cache_queries": 100, "prefix_cache_hits": 0, "waiting": 0}),
        Sample(1.0, {"prefix_cache_queries": 300, "prefix_cache_hits": 150, "waiting": 4}),
        Sample(2.0, {"prefix_cache_queries": 500, "prefix_cache_hits": 300, "waiting": 2}),
    ]
    tel, missing = c.aggregate(0.5, 2.0)
    # counters: last value at t<=0.5 is 100/0, at t<=2.0 is 500/300
    assert tel["prefix_cache_hit_rate"] == pytest.approx(300 / 400)
    assert tel["waiting_max"] == 4 and tel["waiting_mean"] == pytest.approx(3)
    assert "gpu_util_pct" in missing and "waiting" not in missing
