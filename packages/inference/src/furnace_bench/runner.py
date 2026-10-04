"""Benchmark runner: closed-loop concurrency sweeps and open-loop arrival processes.

All requests for the whole run are generated up front from one seeded
generator, so no two measured requests share a prompt by accident (otherwise
a later level would hit prefix-cache entries created by an earlier level).
"""

from __future__ import annotations

import asyncio
import hashlib
import platform
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp
import httpx
import numpy as np

import furnace_bench
from furnace_bench.adapters import Adapter, make_adapter
from furnace_bench.client import RequestTiming, complete_chat, make_session, stream_chat
from furnace_bench.generator import VOCAB, GeneratedRequest, build_requests
from furnace_bench.metrics import summarize_level, tpot_ms
from furnace_bench.schema import (
    ArrivalMode,
    BenchPlan,
    BenchReport,
    BenchTarget,
    EnvManifest,
    LengthMode,
    LevelSummary,
    RequestRecord,
)
from furnace_bench.telemetry.collector import Sample, TelemetryCollector
from furnace_bench.telemetry.nvml import NVMLSampler
from furnace_bench.workload_spec import WorkloadSpec

ProgressFn = Callable[[str], None]


@dataclass
class BenchResult:
    report: BenchReport
    records: list[RequestRecord]
    telemetry: list[Sample] = field(default_factory=list)


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


async def _calibrate_words_per_token(adapter: Adapter, client: httpx.AsyncClient) -> float | None:
    sample = " ".join(VOCAB[i % len(VOCAB)] for i in range(400))
    count = await adapter.tokenize_count(client, sample)
    if not count:
        return None
    return 400 / count


def _to_record(
    idx: int,
    level: float,
    repeat: int,
    req: GeneratedRequest,
    t: RequestTiming,
    t0: float,
    plan: BenchPlan,
) -> RequestRecord:
    usage = t.usage or {}
    in_tok = usage.get("prompt_tokens")
    out_tok = usage.get("completion_tokens")
    source = "server_usage" if out_tok is not None else None
    if out_tok is None and t.ok and t.chunk_times:
        out_tok, source = len(t.chunk_times), "chunk_count"
    tp = tpot_ms(t.ttft_ms, t.e2e_ms, out_tok) if t.ok else None
    rec = RequestRecord(
        idx=idx,
        level=level,
        repeat=repeat,
        ok=t.ok,
        error=t.error,  # type: ignore[arg-type]
        error_detail=t.error_detail,
        send_ts=t.send - t0,
        headers_ms=t.headers_ms,
        first_byte_ms=t.first_byte_ms,
        ttft_ms=t.ttft_ms,
        e2e_ms=t.e2e_ms,
        tpot_ms=tp,
        chunk_gaps_ms=[round(g, 3) for g in t.chunk_gaps_ms],
        n_chunks=len(t.chunk_times),
        input_tokens=in_tok,
        output_tokens=out_tok,
        token_count_source=source,  # type: ignore[arg-type]
        prefix_group=req.prefix_group,
    )
    rec.slo_ok = t.ok and plan.slo.per_request_ok(rec.ttft_ms, rec.tpot_ms, rec.e2e_ms)
    return rec


class _Sender:
    def __init__(self, adapter: Adapter, session: aiohttp.ClientSession, plan: BenchPlan) -> None:
        self.adapter, self.session, self.plan = adapter, session, plan
        self.headers = adapter.headers()

    async def __call__(self, req: GeneratedRequest) -> RequestTiming:
        payload = self.adapter.build_payload(req.messages, req.max_tokens, self.plan, req.extra)
        if self.plan.stream:
            return await stream_chat(
                self.session,
                self.adapter.chat_url,
                payload,
                headers=self.headers,
                ttft_timeout_s=self.plan.ttft_timeout_s,
                total_timeout_s=self.plan.total_timeout_s,
            )
        return await complete_chat(
            self.session,
            self.adapter.chat_url,
            payload,
            headers=self.headers,
            total_timeout_s=self.plan.total_timeout_s,
        )


async def _closed_loop(
    reqs: list[GeneratedRequest], concurrency: int, send: _Sender
) -> list[RequestTiming]:
    results: list[RequestTiming | None] = [None] * len(reqs)
    it = iter(enumerate(reqs))  # shared iterator: asyncio is single-threaded, so this is safe

    async def worker() -> None:
        for i, r in it:
            results[i] = await send(r)

    await asyncio.gather(*(worker() for _ in range(max(1, concurrency))))
    return [r for r in results if r is not None]


async def _open_loop(
    reqs: list[GeneratedRequest],
    rate: float,
    plan: BenchPlan,
    send: _Sender,
    rng: np.random.Generator,
) -> list[RequestTiming]:
    n = len(reqs)
    if plan.arrival == ArrivalMode.gamma and plan.gamma_shape:
        k = plan.gamma_shape
        gaps = rng.gamma(k, 1.0 / (rate * k), size=n)
    else:
        gaps = rng.exponential(1.0 / rate, size=n)
    arrivals = np.cumsum(gaps) - gaps[0]
    loop = asyncio.get_running_loop()
    start = loop.time()
    tasks: list[asyncio.Task[RequestTiming]] = []
    for r, at in zip(reqs, arrivals, strict=True):
        delay = start + float(at) - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        tasks.append(asyncio.create_task(send(r)))
    return list(await asyncio.gather(*tasks))


async def run_benchmark(
    target: BenchTarget,
    spec: WorkloadSpec,
    plan: BenchPlan,
    *,
    sample_gpu: bool = True,
    progress: ProgressFn | None = None,
) -> BenchResult:
    say = progress or (lambda _m: None)
    started_at = datetime.now(timezone.utc).isoformat()
    adapter = make_adapter(target)
    max_conc = int(max(plan.concurrency_levels)) if plan.arrival == ArrivalMode.closed_loop else 256
    limits = httpx.Limits(max_connections=8)
    timeout = httpx.Timeout(10.0)
    notes: list[str] = []

    # httpx: untimed probes (models, tokenize, metrics). aiohttp: the timed request path.
    async with (
        httpx.AsyncClient(limits=limits, timeout=timeout) as client,
        make_session(max_conc + 8, plan.total_timeout_s) as session,
    ):
        info = await adapter.info(client)
        wpt = await _calibrate_words_per_token(adapter, client)
        if wpt is None:
            wpt = 1.0
            notes.append(
                "Prompt lengths are word-count targets (server exposes no tokenizer); "
                "measured input tokens come from server usage."
            )
        else:
            notes.append(
                f"Prompt lengths calibrated with the server tokenizer ({wpt:.3f} words/token)."
            )
        if plan.length_mode == LengthMode.fixed and not adapter.supports_ignore_eos:
            notes.append(
                f"{adapter.name} cannot ignore EOS: max_tokens is an upper bound, so output "
                "lengths (and TPOT comparisons) are not pinned."
            )
        if spec.synthetic:
            notes.append(f"Workload '{spec.name}' is SYNTHETIC (source: {spec.source.value}).")

        per_slot = plan.warmup_requests + plan.requests_per_level
        n_slots = len(plan.concurrency_levels) * plan.repeats
        all_reqs = build_requests(spec, plan, per_slot * n_slots, words_per_token=wpt)

        nvml = NVMLSampler() if sample_gpu else None
        if nvml is not None and nvml.available:
            notes.append(
                f"GPU telemetry from NVML on the benchmark host: {nvml.name}. "
                "Valid only if the endpoint is served from this host."
            )
        t0 = time.perf_counter()
        collector = TelemetryCollector(
            t0=t0,
            scrape=(lambda: adapter.scrape(client)) if adapter.metrics_url else None,
            nvml=nvml,
            interval_s=plan.telemetry_interval_s,
        )
        collector.start()
        send = _Sender(adapter, session, plan)
        rng = np.random.default_rng(plan.seed + 1)
        records: list[RequestRecord] = []
        summaries: list[LevelSummary] = []
        slot = 0
        try:
            for repeat in range(plan.repeats):
                for level in plan.concurrency_levels:
                    chunk = all_reqs[slot * per_slot : (slot + 1) * per_slot]
                    slot += 1
                    warm, measured = chunk[: plan.warmup_requests], chunk[plan.warmup_requests :]
                    label = f"repeat {repeat + 1}/{plan.repeats} level {level:g}"
                    if warm:
                        await _closed_loop(warm, int(min(level, len(warm))) or 1, send)
                    say(f"{label}: measuring {len(measured)} requests")
                    if plan.arrival == ArrivalMode.closed_loop:
                        timings = await _closed_loop(measured, int(level), send)
                    else:
                        timings = await _open_loop(measured, float(level), plan, send, rng)
                    base_idx = len(records)
                    recs = [
                        _to_record(base_idx + i, level, repeat, r, t, t0, plan)
                        for i, (r, t) in enumerate(zip(measured, timings, strict=True))
                    ]
                    records.extend(recs)
                    summary = summarize_level(
                        recs, level=level, repeat=repeat, slo=plan.slo, seed=plan.seed
                    )
                    if recs:
                        w_start = min(r.send_ts for r in recs)
                        w_end = max(r.send_ts + (r.e2e_ms or 0) / 1000 for r in recs)
                        summary.telemetry, summary.not_exposed = collector.aggregate(w_start, w_end)
                    summaries.append(summary)
                    say(
                        f"{label}: ok {summary.n_ok}/{summary.n}, "
                        f"TTFT p95 {summary.ttft_ms.p95 or float('nan'):.1f} ms, "
                        f"{summary.request_throughput_rps:.2f} req/s"
                    )
                    if plan.cooldown_s > 0:
                        await asyncio.sleep(plan.cooldown_s)
        finally:
            await collector.stop()

    env = EnvManifest(
        furnace_bench_version=furnace_bench.__version__,
        furnace_git_sha=_git_sha(),
        python=sys.version.split()[0],
        platform=platform.platform(),
        gpu=nvml.name if nvml and nvml.available else None,
        gpu_driver=nvml.driver if nvml and nvml.available else None,
        engine=adapter.name,
        engine_version=info.get("engine_version"),
        model_revision=info.get("model_root"),
        started_at=started_at,
        hostname_hash=hashlib.sha256(platform.node().encode()).hexdigest()[:12],
    )
    report = BenchReport(
        run_id=uuid.uuid4().hex[:12],
        target=target,
        plan=plan,
        workload_name=spec.name,
        workload_synthetic=spec.synthetic,
        env=env,
        levels=summaries,
        notes=notes,
    )
    return BenchResult(report=report, records=records, telemetry=collector.samples)
