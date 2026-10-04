"""Measurement validation against a deterministic mock server in its own process.

perf_counter is system-wide monotonic, so the server's own timestamps (GET
/_records) can be compared with the client's: the difference is the client's
measurement overhead, which we bound here.
"""

import asyncio
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import numpy as np
import pytest

from furnace_bench.runner import run_benchmark
from furnace_bench.schema import BenchPlan, BenchTarget
from furnace_bench.workload_spec import SLO, Distribution, WorkloadSource, WorkloadSpec

SPEC = WorkloadSpec(
    source=WorkloadSource.synthetic,
    synthetic=True,
    input_tokens=Distribution(p50=64, mean=64),
    output_tokens=Distribution(p50=32, mean=32),
)


@contextmanager
def mock_server(*args: str) -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "furnace_bench.cli", "mock", "--port", "0", *args],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        line = proc.stdout.readline()
        base_url = line.split(" on ", 1)[1].split(" ", 1)[0]
        yield base_url
    finally:
        proc.terminate()
        proc.wait(10)


def _run(base_url, level, n=48, warmup=None, slo=None, **plan_kw):
    target = BenchTarget(base_url=base_url, model="mock")
    plan = BenchPlan(
        concurrency_levels=[level],
        requests_per_level=n,
        warmup_requests=level if warmup is None else warmup,
        cooldown_s=0,
        slo=slo or SLO(),
        seed=11,
        **plan_kw,
    )
    return asyncio.run(run_benchmark(target, SPEC, plan, sample_gpu=False))


def _server_records(base_url, n):
    rows = httpx.get(base_url.removesuffix("/v1") + "/_records").json()
    return sorted(rows, key=lambda r: r["recv"])[-n:]  # measured requests follow warmup


@pytest.mark.parametrize("level", [1, 4, 16])
def test_client_timing_matches_server_timing(level):
    with mock_server("--ttft-ms", "40", "--tpot-ms", "8") as url:
        result = _run(url, level)
        srv = _server_records(url, len(result.records))
    recs = result.records
    assert all(r.ok for r in recs), [r.error_detail for r in recs if not r.ok]
    assert all(r.output_tokens == 32 and r.token_count_source == "server_usage" for r in recs)

    srv_ttft = np.array([(s["first_token"] - s["recv"]) * 1000 for s in srv])
    srv_tpot = np.array(
        [(s["last_token"] - s["first_token"]) * 1000 / (s["n_tokens"] - 1) for s in srv]
    )
    cli_ttft = np.array([r.ttft_ms for r in recs])
    cli_tpot = np.array([r.tpot_ms for r in recs])

    overhead_p50 = float(np.percentile(cli_ttft, 50) - np.percentile(srv_ttft, 50))
    overhead_p95 = float(np.percentile(cli_ttft, 95) - np.percentile(srv_ttft, 95))
    print(f"\nlevel={level} TTFT overhead p50={overhead_p50:.2f} ms p95={overhead_p95:.2f} ms")
    # Non-negative overhead also proves the role-only first chunk is not counted as TTFT
    # (that chunk is sent at receipt, ~40 ms before the first token).
    assert 0.0 <= overhead_p50 < 2.0
    assert abs(overhead_p95) < 5.0
    assert abs(np.median(cli_tpot) - np.median(srv_tpot)) / np.median(srv_tpot) < 0.05


def test_server_queueing_shows_up_in_ttft_and_goodput():
    with mock_server("--ttft-ms", "20", "--tpot-ms", "5", "--max-concurrency", "2") as url:
        free = _run(url, 1, n=16, slo=SLO(ttft_p95_ms=100))
        queued = _run(url, 8, n=32, slo=SLO(ttft_p95_ms=100))
    s1, s8 = free.report.levels[0], queued.report.levels[0]
    assert s1.ttft_ms.p95 is not None and s8.ttft_ms.p95 is not None
    # 8 workers share 2 generation slots of ~175 ms each, so most requests queue.
    assert s8.ttft_ms.p95 > 3 * s1.ttft_ms.p95
    assert s1.goodput_ratio == 1.0
    assert s8.goodput_ratio is not None and s8.goodput_ratio < 0.5


def test_connect_errors_are_classified():
    res = _run("http://127.0.0.1:9/v1", 1, n=2, warmup=0)
    assert all(r.error == "connect" for r in res.records)
    assert res.report.levels[0].failure_rate == 1.0


def test_ttft_timeouts_are_classified():
    with mock_server("--ttft-ms", "500", "--tpot-ms", "1") as url:
        res = _run(url, 1, n=2, warmup=0, ttft_timeout_s=0.1)
    assert all(r.error == "ttft_timeout" for r in res.records), [r.error for r in res.records]
    assert res.report.levels[0].timeout_rate == 1.0
