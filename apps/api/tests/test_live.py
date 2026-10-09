"""Live lab telemetry, the recorded fallback, and on-demand runs against the mock server."""

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from furnace.settings import get_settings
from furnace_api.routers import live
from furnace_api.routers.bench import W1

REPO_BENCH = Path(__file__).resolve().parents[3] / "bench"


@pytest.fixture
def bench(tmp_path, monkeypatch):
    camp = tmp_path / "results" / "2026-10-06" / "rq4"
    run = camp / "runs" / "abc"
    run.mkdir(parents=True)
    (camp / "runs.json").write_text(
        json.dumps(
            {
                "runs": [
                    {"config": "pc-off_seqs-32", "repeat": 0, "run_dir": "bench/x"},
                    {
                        "config": "pc-on_seqs-32",
                        "repeat": 0,
                        "run_dir": "bench/results/2026-10-06/rq4/runs/abc",
                    },
                ]
            }
        )
    )
    tel = [
        {"t": 0.1, "running": 0, "waiting": 0, "kv_cache_usage": 0.0, "prefix_cache_queries": 0,
         "prefix_cache_hits": 0, "gpu_sm_clock_mhz": 210.0},
        {"t": 1.2, "running": 2, "waiting": 1, "kv_cache_usage": 0.1, "prefix_cache_queries": 100,
         "prefix_cache_hits": 80, "gpu_sm_clock_mhz": 780.0},
        {"t": 1.6, "running": 1, "waiting": 0, "kv_cache_usage": 0.3, "prefix_cache_queries": 200,
         "prefix_cache_hits": 170, "gpu_sm_clock_mhz": 780.0},
    ]  # fmt: skip
    (run / "telemetry.jsonl").write_text("\n".join(json.dumps(t) for t in tel))
    reqs = [  # 4 chunks at 1.0, 1.5, 2.0, 2.5 s carrying 8 tokens
        {"idx": 0, "level": 1.0, "repeat": 0, "ok": True, "send_ts": 0.9, "ttft_ms": 100,
         "e2e_ms": 1600, "chunk_gaps_ms": [500, 500, 500], "n_chunks": 4, "output_tokens": 8},
    ]  # fmt: skip
    (run / "requests.jsonl").write_text("\n".join(json.dumps(r) for r in reqs))
    report = {
        "run_id": "abc",
        "env": {"started_at": "2026-10-06T00:00:00", "gpu": "GPU", "engine": "vllm"},
        "levels": [
            {
                "level": 1.0,
                "repeat": 0,
                "ttft_ms": {"p95": 100.0},
                "telemetry": {"prefix_cache_hit_rate": 0.85, "gpu_sm_clock_mhz_mean": 780.0},
            }
        ],
    }
    (run / "report.json").write_text(json.dumps(report))
    (tmp_path / W1).parent.mkdir(parents=True)
    shutil.copy(REPO_BENCH / W1, tmp_path / W1)
    monkeypatch.setenv("FURNACE_BENCH_DIR", str(tmp_path))
    monkeypatch.setenv("FURNACE_LIVE_LAB", "true")
    get_settings.cache_clear()
    live._recorded.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(live.router)
    return app


def test_recorded_fallback_is_derived_from_the_run_files(bench):
    r = TestClient(_app()).get("/api/live/recorded").json()
    assert r["source"] == "bench/results/2026-10-06/rq4/runs/abc"
    assert r["config"] == "pc-on_seqs-32" and r["campaign"] == "2026-10-06"
    s0, s1 = r["series"]
    assert s0["t"] == 0 and s0["prefix_hit_rate"] is None  # no earlier window
    # second 1: counters went 0 -> 200 queries, 0 -> 170 hits
    assert s1["prefix_hit_rate"] == pytest.approx(0.85)
    assert s1["running"] == 2 and s1["kv_cache_usage"] == pytest.approx(0.2)
    # chunks at 1.0 and 1.5 s fall in second 1 (2 tokens each); 2.0, 2.5 in second 2 (no sample)
    assert s1["gen_tok_s"] == 4.0
    assert r["levels"] == [
        {"level": 1.0, "t0": 0.9, "t1": 2.5, "ttft_p95_ms": 100.0, "prefix_hit_rate": 0.85,
         "sm_clock_mhz": 780.0}
    ]  # fmt: skip


def test_recorded_404_without_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("FURNACE_BENCH_DIR", str(tmp_path))
    get_settings.cache_clear()
    assert TestClient(_app()).get("/api/live/recorded").status_code == 404
    get_settings.cache_clear()


def test_window_rates_from_counter_deltas_and_restart():
    s = live.LabSampler()
    raw = {
        "vllm:num_requests_running": 3.0,
        "vllm:num_requests_waiting": 1.0,
        "vllm:kv_cache_usage_perc": 0.25,
        "vllm:prefix_cache_queries_total": 1000.0,
        "vllm:prefix_cache_hits_total": 900.0,
        "vllm:generation_tokens_total": 500.0,
    }
    first = s._derive(raw, now=10.0)
    assert first["prefix_hit_rate"] is None and first["gen_tok_s"] is None
    assert first["prefix_hit_rate_total"] == pytest.approx(0.9)
    nxt = {**raw, "vllm:prefix_cache_queries_total": 1200.0, "vllm:prefix_cache_hits_total": 1050.0,
           "vllm:generation_tokens_total": 700.0}  # fmt: skip
    second = s._derive(nxt, now=12.0)
    assert second["prefix_hit_rate"] == pytest.approx(0.75)
    assert second["gen_tok_s"] == pytest.approx(100.0)
    assert second["running"] == 3.0 and second["kv_cache_usage"] == 0.25
    # server restarted: counters went backwards, so no window rate rather than a negative one
    restarted = s._derive({**raw, "vllm:generation_tokens_total": 10.0}, now=13.0)
    assert restarted["gen_tok_s"] is None
    # idle window: no queries -> no hit rate (not 0%)
    idle = s._derive({**raw, "vllm:generation_tokens_total": 10.0}, now=14.0)
    assert idle["prefix_hit_rate"] is None and idle["gen_tok_s"] == 0.0


def test_sampler_reports_offline_endpoint(monkeypatch):
    monkeypatch.setenv("FURNACE_LAB_BASE_URL", "http://127.0.0.1:9/v1")
    get_settings.cache_clear()
    out = asyncio.run(live.LabSampler().sample())
    assert out["online"] is False and out["lab"] is None and out["error"]
    get_settings.cache_clear()


def test_telemetry_stream_disabled(monkeypatch):
    monkeypatch.setenv("FURNACE_LIVE_LAB", "false")
    get_settings.cache_clear()
    with TestClient(_app()) as c:
        body = c.get("/api/live/telemetry").text
        assert "event: disabled" in body
        assert c.post("/api/live/bench").status_code == 503
    get_settings.cache_clear()


def test_start_bench_refuses_offline_lab(bench, monkeypatch):
    monkeypatch.setenv("FURNACE_LAB_BASE_URL", "http://127.0.0.1:9/v1")
    get_settings.cache_clear()
    assert TestClient(_app()).post("/api/live/bench").status_code == 503


def _events(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_live_run_streams_every_request_then_the_summary(bench, monkeypatch):
    proc = subprocess.Popen(
        [sys.executable, "-m", "furnace_bench.cli", "mock", "--port", "0",
         "--ttft-ms", "5", "--tpot-ms", "1"],
        stdout=subprocess.PIPE, text=True,
    )  # fmt: skip
    try:
        assert proc.stdout is not None
        url = proc.stdout.readline().split(" on ", 1)[1].split(" ", 1)[0]
        monkeypatch.setenv("FURNACE_LAB_BASE_URL", url)
        monkeypatch.setattr(live, "_ACTIVE", None)
        monkeypatch.setattr(live, "_LAST_FINISHED", 0.0)
        monkeypatch.setattr(live, "_RATE", live.defaultdict(live.deque))
        get_settings.cache_clear()
        monkeypatch.setattr(live, "_RUNS", {})
        with TestClient(_app()) as c:
            assert c.get("/api/live/bench/latest").json()["run_id"] is None
            run_id = c.post("/api/live/bench").json()["run_id"]
            assert c.post("/api/live/bench").status_code == 409  # one run at a time
            evs = _events(c.get(f"/api/live/bench/{run_id}/events").text)
            assert c.get("/api/live/bench/latest").json()["status"] == "done"
            # a reconnecting viewer resumes after the last event it saw
            tail = c.get(f"/api/live/bench/{run_id}/events", headers={"Last-Event-ID": "3"}).text
            assert _events(tail) == evs[4:]
            # cooling down after a run
            assert c.post("/api/live/bench").status_code == 429
    finally:
        proc.terminate()
        proc.wait(10)
    assert evs[0]["type"] == "start" and evs[-1]["type"] == "done", evs[-1]
    reqs = [e for e in evs if e["type"] == "request"]
    n = len(live.LIVE_LEVELS) * live.LIVE_REQUESTS
    assert len(reqs) == n and all(e["ok"] and e["ttft_ms"] > 0 for e in reqs)
    assert {e["level"] for e in reqs} == set(live.LIVE_LEVELS)
    done = evs[-1]
    assert [lv["n"] for lv in done["levels"]] == [live.LIVE_REQUESTS] * len(live.LIVE_LEVELS)
    assert (bench / done["saved_to"].removeprefix("bench/") / "report.json").is_file()


def test_rate_limit_per_address(monkeypatch):
    monkeypatch.setattr(live, "_RATE", live.defaultdict(live.deque))
    for _ in range(live.PER_IP_LIMIT):
        live._rate_limit("1.2.3.4")
    with pytest.raises(live.HTTPException) as e:
        live._rate_limit("1.2.3.4")
    assert e.value.status_code == 429
    live._rate_limit("5.6.7.8")


def test_stream_sends_recent_history_first(monkeypatch):
    monkeypatch.setenv("FURNACE_LIVE_LAB", "true")
    get_settings.cache_clear()
    sampler = live.LabSampler()
    sampler.history.extend({"ts": float(i), "online": True, "n": i} for i in range(3))

    async def newest():
        return {"ts": 3.0, "online": True, "n": 3}

    monkeypatch.setattr(sampler, "sample", newest)
    monkeypatch.setattr(live, "SAMPLER", sampler)
    monkeypatch.setattr(live, "STREAM_SECONDS", 0.5)
    body = TestClient(_app()).get("/api/live/telemetry").text
    ns = [json.loads(x[6:])["n"] for x in body.splitlines() if x.startswith("data: ")]
    assert ns[:3] == [0, 1, 3]  # history minus its newest entry, then live samples
    get_settings.cache_clear()
