"""Live lab telemetry and small on-demand benchmark runs.

Everything streamed here is read from the running system: the lab vLLM's Prometheus
/metrics and NVML on this host. When the lab endpoint is unreachable the stream says
so, and /api/live/recorded serves telemetry recorded during the RQ4 campaign, labeled
with the run it came from. Nothing is interpolated or simulated.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import itertools
import json
import math
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import APIRouter, HTTPException, Request
from furnace.settings import get_settings
from furnace_bench.adapters.engines import VLLMAdapter
from furnace_bench.report.writer import write_result
from furnace_bench.runner import run_benchmark
from furnace_bench.schema import AdapterName, BenchPlan, BenchTarget, LengthMode, RequestRecord
from furnace_bench.telemetry.nvml import NVMLSampler
from furnace_bench.telemetry.prom import parse_prometheus
from furnace_bench.workload_spec import SLO, WorkloadSpec
from sse_starlette.sse import EventSourceResponse

from furnace_api.routers.bench import CAMPAIGN, W1, bench_dir
from furnace_api.sse import sse

router = APIRouter(prefix="/api/live")

METRICS: dict[str, list[str]] = {
    **VLLMAdapter.metric_map,
    "generation_tokens": ["vllm:generation_tokens_total"],
}
STREAM_SECONDS = 900  # one SSE connection; EventSource reconnects after this
RECORDED_CONFIG = "pc-on_seqs-32"  # the configuration /lab shows by default


def _lab_root() -> str:
    return get_settings().lab_base_url.rstrip("/").removesuffix("/v1")


def _pick(raw: dict[str, float], names: list[str]) -> float | None:
    return next((raw[n] for n in names if n in raw), None)


def _delta(cur: float | None, prev: float | None) -> float | None:
    """Counter increase; None across a server restart (counter went backwards)."""
    if cur is None or prev is None or cur < prev:
        return None
    return cur - prev


class LabSampler:
    """One shared poller, so N open dashboards cost one scrape per interval, not N."""

    def __init__(self, interval_s: float = 1.0) -> None:
        self.interval_s = interval_s
        self._lock = asyncio.Lock()
        self._last: dict[str, Any] | None = None
        self._last_at = 0.0
        self._prev: tuple[float, dict[str, float | None]] | None = None
        self._nvml: NVMLSampler | None = None
        self._nvml_tried = False
        # the last ~90 s of real samples, so a new viewer sees history, not one point
        self.history: deque[dict[str, Any]] = deque(maxlen=90)

    def _gpu(self) -> dict[str, Any] | None:
        if not self._nvml_tried:
            self._nvml_tried = True
            s = NVMLSampler()
            self._nvml = s if s.available else None
        if self._nvml is None:
            return None
        m = self._nvml.sample()
        return {
            "name": self._nvml.name,
            "sm_clock_mhz": m.get("gpu_sm_clock_mhz"),
            "power_w": m.get("gpu_power_w"),
            "temp_c": m.get("gpu_temp_c"),
            "util_pct": m.get("gpu_util_pct"),
            "mem_used_mb": m.get("gpu_mem_used_mb"),
        }

    def _derive(self, raw: dict[str, float], now: float) -> dict[str, Any]:
        cur = {k: _pick(raw, names) for k, names in METRICS.items()}
        q, h = cur["prefix_cache_queries"], cur["prefix_cache_hits"]
        lab: dict[str, Any] = {
            "running": cur["running"],
            "waiting": cur["waiting"],
            "kv_cache_usage": cur["kv_cache_usage"],
            "prefix_hit_rate": None,  # over the last window; None when nothing was queried
            "prefix_hit_rate_total": (h / q) if q and h is not None else None,
            "gen_tok_s": None,
            "window_s": None,
        }
        if self._prev is not None:
            t_prev, prev = self._prev
            dt = now - t_prev
            dq = _delta(q, prev["prefix_cache_queries"])
            dh = _delta(h, prev["prefix_cache_hits"])
            if dq and dh is not None:
                lab["prefix_hit_rate"] = dh / dq
            dg = _delta(cur["generation_tokens"], prev["generation_tokens"])
            if dg is not None and dt > 0:
                lab["gen_tok_s"] = dg / dt
            lab["window_s"] = round(dt, 3)
        self._prev = (now, cur)
        return lab

    async def sample(self) -> dict[str, Any]:
        async with self._lock:
            now = time.monotonic()
            if self._last is not None and now - self._last_at < self.interval_s * 0.9:
                return self._last
            out: dict[str, Any] = {"ts": time.time(), "online": False, "lab": None, "error": None}
            try:
                async with httpx.AsyncClient(timeout=1.5) as c:
                    r = await c.get(f"{_lab_root()}/metrics")
                    r.raise_for_status()
            except (httpx.HTTPError, OSError) as exc:
                out["error"] = type(exc).__name__
                self._prev = None
            else:
                out["online"] = True
                out["lab"] = self._derive(parse_prometheus(r.text), now)
            out["gpu"] = await asyncio.to_thread(self._gpu)
            self._last, self._last_at = out, now
            self.history.append(out)
            return out

    async def run_forever(self) -> None:
        """Background poller (started with the API when live_lab is on)."""
        while True:
            t0 = time.monotonic()
            with contextlib.suppress(Exception):
                await self.sample()
            await asyncio.sleep(max(0.05, self.interval_s - (time.monotonic() - t0)))


SAMPLER = LabSampler()


@router.get("/status")
async def status() -> dict[str, Any]:
    s = get_settings()
    return {
        "live_lab": s.live_lab,
        "active_run": _ACTIVE.id if _ACTIVE and _ACTIVE.status == "running" else None,
    }


@router.get("/telemetry")
async def telemetry(request: Request) -> EventSourceResponse:
    enabled = get_settings().live_lab

    async def stream() -> AsyncIterator[dict[str, str]]:
        if not enabled:
            yield {"event": "disabled", "data": json.dumps({"online": False, "disabled": True})}
            return
        for past in list(SAMPLER.history)[:-1]:  # backlog first: real samples, oldest first
            yield {"event": "sample", "data": json.dumps(past)}
        deadline = time.monotonic() + STREAM_SECONDS
        while time.monotonic() < deadline and not await request.is_disconnected():
            yield {"event": "sample", "data": json.dumps(await SAMPLER.sample())}
            await asyncio.sleep(SAMPLER.interval_s)

    return sse(stream())


# ------------------------------------------------------------- recorded fallback


def _rq4_runs() -> tuple[str, dict[str, Any]] | None:
    root = bench_dir() / "results"
    for d in sorted(root.iterdir() if root.is_dir() else [], reverse=True):
        idx = d / "rq4" / "runs.json"
        if d.is_dir() and CAMPAIGN.match(d.name) and idx.is_file():
            return d.name, json.loads(idx.read_text(encoding="utf-8"))
    return None


def _jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _tokens_per_second(reqs: list[dict[str, Any]]) -> dict[int, float]:
    """Output tokens per 1 s bin, placed at each streamed chunk's client timestamp."""
    bins: dict[int, float] = defaultdict(float)
    for r in reqs:
        if not r.get("ok") or r.get("ttft_ms") is None or not r.get("n_chunks"):
            continue
        per_chunk = (r.get("output_tokens") or 0) / r["n_chunks"]
        t = r["send_ts"] + r["ttft_ms"] / 1000
        times = itertools.accumulate((g / 1000 for g in r.get("chunk_gaps_ms") or []), initial=t)
        for ct in times:
            bins[math.floor(ct)] += per_chunk
    return bins


@functools.lru_cache(maxsize=4)
def _recorded(run_dir: str, mtime: float) -> dict[str, Any]:
    d = bench_dir() / run_dir
    tel = _jsonl(d / "telemetry.jsonl")
    reqs = _jsonl(d / "requests.jsonl")
    report = json.loads((d / "report.json").read_text(encoding="utf-8"))
    toks = _tokens_per_second(reqs)
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in tel:
        buckets[math.floor(s["t"])].append(s)
    series: list[dict[str, Any]] = []
    prev_last: dict[str, Any] | None = None
    for sec in sorted(buckets):
        ss = buckets[sec]
        last = ss[-1]

        def mean(k: str, ss: list[dict[str, Any]] = ss) -> float | None:
            v = [s[k] for s in ss if s.get(k) is not None]
            return sum(v) / len(v) if v else None

        hit = None
        if prev_last is not None:
            dq = _delta(last.get("prefix_cache_queries"), prev_last.get("prefix_cache_queries"))
            dh = _delta(last.get("prefix_cache_hits"), prev_last.get("prefix_cache_hits"))
            if dq and dh is not None:
                hit = dh / dq
        prev_last = last
        series.append(
            {
                "t": sec,
                "running": max(s.get("running") or 0 for s in ss),
                "waiting": max(s.get("waiting") or 0 for s in ss),
                "kv_cache_usage": mean("kv_cache_usage"),
                "prefix_hit_rate": hit,
                "gen_tok_s": round(toks.get(sec, 0.0), 1),
                "sm_clock_mhz": mean("gpu_sm_clock_mhz"),
                "power_w": mean("gpu_power_w"),
                "temp_c": mean("gpu_temp_c"),
            }
        )
    levels = []
    for lv in report["levels"]:
        rs = [r for r in reqs if r["level"] == lv["level"] and r["repeat"] == lv["repeat"]]
        tel_lv = lv.get("telemetry") or {}
        levels.append(
            {
                "level": lv["level"],
                "t0": min(r["send_ts"] for r in rs) if rs else None,
                "t1": max(r["send_ts"] + (r["e2e_ms"] or 0) / 1000 for r in rs) if rs else None,
                "ttft_p95_ms": lv["ttft_ms"].get("p95"),
                "prefix_hit_rate": tel_lv.get("prefix_cache_hit_rate"),
                "sm_clock_mhz": tel_lv.get("gpu_sm_clock_mhz_mean"),
            }
        )
    return {
        "source": f"bench/{run_dir}",
        "run_id": report["run_id"],
        "started_at": report["env"]["started_at"],
        "gpu": report["env"].get("gpu"),
        "engine": f"{report['env'].get('engine')} {report['env'].get('engine_version') or ''}".strip(),
        "series": series,
        "levels": levels,
        "notes": [
            "Telemetry sampled every ~0.3 s during the run, shown per second (gauges: max for "
            "queue depth, mean otherwise; prefix-cache hit rate from counter deltas).",
            "Output tokens/s placed at each streamed chunk's client timestamp.",
        ],
    }


@router.get("/recorded")
def recorded() -> dict[str, Any]:
    found = _rq4_runs()
    if found is None:
        raise HTTPException(404, "no recorded RQ4 runs")
    campaign, index = found
    runs = [r for r in index.get("runs", []) if r.get("config") == RECORDED_CONFIG]
    if not runs:
        raise HTTPException(404, f"no recorded {RECORDED_CONFIG} run")
    run = sorted(runs, key=lambda r: r.get("repeat", 0))[0]
    # run_dir is relative to the repo root ("bench/results/..."); bench_dir() is <root>/bench
    run_dir = run["run_dir"].removeprefix("bench/")
    report = bench_dir() / run_dir / "report.json"
    if not report.is_file():
        raise HTTPException(404, "recorded run files missing")
    out = _recorded(run_dir, report.stat().st_mtime)
    return {**out, "campaign": campaign, "config": run["config"], "repeat": run.get("repeat")}


# ------------------------------------------------------------- on-demand bench runs

LIVE_LEVELS = (1.0, 2.0, 4.0, 8.0)
LIVE_REQUESTS = 20
LIVE_WARMUP = 2
LIVE_SLO_MS = 500.0  # same TTFT SLO as the RQ4 campaign
RUN_TIMEOUT_S = 300
PER_IP_LIMIT, PER_IP_WINDOW_S = 3, 600
COOLDOWN_S = 15  # between runs, so the GPU is back at idle before the next one


@dataclass
class LiveRun:
    id: str
    started: float
    status: str = "running"  # running | done | failed
    events: list[dict[str, Any]] = field(default_factory=list)
    finished: float | None = None


_RUNS: dict[str, LiveRun] = {}
_ACTIVE: LiveRun | None = None
_LAST_FINISHED = 0.0
_RATE: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit(ip: str) -> None:
    now = time.monotonic()
    hits = _RATE[ip]
    while hits and now - hits[0] > PER_IP_WINDOW_S:
        hits.popleft()
    if len(hits) >= PER_IP_LIMIT:
        raise HTTPException(
            429, f"At most {PER_IP_LIMIT} runs per {PER_IP_WINDOW_S // 60} minutes."
        )
    hits.append(now)


def _record_event(r: RequestRecord) -> dict[str, Any]:
    return {
        "type": "request",
        "idx": r.idx,
        "level": r.level,
        "ok": r.ok,
        "error": r.error,
        "ttft_ms": r.ttft_ms,
        "e2e_ms": r.e2e_ms,
        "t": r.send_ts + (r.e2e_ms or 0) / 1000,
        "slo_ok": r.slo_ok,
    }


async def _execute(run: LiveRun, target: BenchTarget) -> None:
    global _LAST_FINISHED
    spec_path = bench_dir() / W1
    spec = WorkloadSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))
    plan = BenchPlan(
        concurrency_levels=list(LIVE_LEVELS),
        requests_per_level=LIVE_REQUESTS,
        warmup_requests=LIVE_WARMUP,
        length_mode=LengthMode.fixed,
        cooldown_s=0,
        seed=int(time.time()) % 100_000,
        slo=SLO(ttft_p95_ms=LIVE_SLO_MS),
    )
    run.events.append(
        {
            "type": "start",
            "levels": list(LIVE_LEVELS),
            "requests_per_level": LIVE_REQUESTS,
            "slo_ttft_ms": LIVE_SLO_MS,
            "workload": f"bench/{W1}",
            "target": target.base_url,
        }
    )
    try:
        res = await asyncio.wait_for(
            run_benchmark(
                target,
                spec,
                plan,
                on_record=lambda r: run.events.append(_record_event(r)),
                progress=lambda m: run.events.append({"type": "log", "msg": m}),
            ),
            RUN_TIMEOUT_S,
        )
    except Exception as exc:  # reported to the viewer as-is
        run.status = "failed"
        run.events.append({"type": "error", "msg": f"{type(exc).__name__}: {str(exc)[:300]}"})
    else:
        out = bench_dir() / ".cache" / "live-runs"
        path = await asyncio.to_thread(write_result, res, out)
        run.events.append(
            {
                "type": "done",
                "run_id": res.report.run_id,
                "saved_to": f"bench/{path.relative_to(bench_dir()).as_posix()}",
                "gpu": res.report.env.gpu,
                "levels": [
                    {
                        "level": lv.level,
                        "n": lv.n,
                        "n_ok": lv.n_ok,
                        "ttft_p50_ms": lv.ttft_ms.p50,
                        "ttft_p95_ms": lv.ttft_ms.p95,
                        "rps": lv.request_throughput_rps,
                        "output_tok_s": lv.output_tok_s,
                        "goodput_ratio": lv.goodput_ratio,
                        "prefix_hit_rate": (lv.telemetry or {}).get("prefix_cache_hit_rate"),
                        "sm_clock_mhz": (lv.telemetry or {}).get("gpu_sm_clock_mhz_mean"),
                    }
                    for lv in res.report.levels
                ],
            }
        )
        run.status = "done"
    finally:
        run.finished = time.time()
        _LAST_FINISHED = time.monotonic()


@router.post("/bench", status_code=201)
async def start_bench(request: Request) -> dict[str, Any]:
    global _ACTIVE
    s = get_settings()
    if not s.live_lab:
        raise HTTPException(503, "Live runs are disabled on this deployment.")
    if _ACTIVE is not None and _ACTIVE.status == "running":
        raise HTTPException(409, "A run is already in progress; watch it instead.")
    wait = COOLDOWN_S - (time.monotonic() - _LAST_FINISHED)
    if _LAST_FINISHED and wait > 0:
        raise HTTPException(429, f"GPU cooling down; try again in {math.ceil(wait)} s.")
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            (await c.get(f"{s.lab_base_url.rstrip('/')}/models")).raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(503, "Lab endpoint offline.") from exc
    _rate_limit(request.client.host if request.client else "unknown")
    run = LiveRun(id=uuid.uuid4().hex[:12], started=time.time())
    _RUNS[run.id] = run
    for old in list(_RUNS)[:-5]:  # keep the last few for reconnecting viewers
        _RUNS.pop(old, None)
    _ACTIVE = run
    target = BenchTarget(
        adapter=AdapterName.vllm, base_url=s.lab_base_url, model=s.lab_model, label="lab vLLM"
    )
    task = asyncio.create_task(_execute(run, target))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return {"run_id": run.id}


_TASKS: set[asyncio.Task[None]] = set()


@router.get("/bench/latest")
def latest_bench() -> dict[str, Any]:
    if not _RUNS:  # not an error: nothing has run since the API started
        return {"run_id": None, "status": None, "started": None}
    run = list(_RUNS.values())[-1]
    return {"run_id": run.id, "status": run.status, "started": run.started}


@router.get("/bench/{run_id}/events")
async def bench_events(run_id: str, request: Request) -> EventSourceResponse:
    run = _RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    start = 0
    with contextlib.suppress(ValueError):
        start = int(request.headers.get("last-event-id", "-1")) + 1

    async def stream() -> AsyncIterator[dict[str, str]]:
        i = start
        while True:
            while i < len(run.events):
                ev = run.events[i]
                yield {"event": ev["type"], "id": str(i), "data": json.dumps(ev)}
                i += 1
            if run.status != "running" or await request.is_disconnected():
                return
            await asyncio.sleep(0.1)

    return sse(stream())
