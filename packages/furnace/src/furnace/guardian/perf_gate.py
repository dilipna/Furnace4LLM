"""Performance gate: benchmark the prompts each revision actually produces.

Prompts are rendered from each revision's own harness inside the sandbox, then
replayed by furnace-bench against the inference endpoint. Every run appends a
unique per-run reference to each question, so the only cacheable sharing between
requests is the prompt prefix the code produces (no request is ever repeated
verbatim, within or across runs). Results are compared against a regression
budget (warn/block thresholds as fractions of the baseline).
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from furnace_bench.runner import run_benchmark
from furnace_bench.schema import BenchPlan, BenchReport, BenchTarget, LengthMode, PromptMode
from furnace_bench.workload_spec import SLO, WorkloadSource, WorkloadSpec

from furnace.guardian.repair.regression import render_in_sandbox


@dataclass
class GatePolicy:
    warn_pct: float = 10.0
    block_pct: float = 25.0
    metric: str = "ttft_p95_ms"


class MetricSource(Protocol):
    def metric(self, name: str) -> float | None: ...


@dataclass
class VariantResult:
    name: str
    report: BenchReport

    def metric(self, name: str) -> float | None:
        lvl = self.report.levels[0]
        return {
            "ttft_p95_ms": lvl.ttft_ms.p95,
            "ttft_p50_ms": lvl.ttft_ms.p50,
            "e2e_p95_ms": lvl.e2e_ms.p95,
            "goodput_rps": lvl.slo_goodput_rps,
            "throughput_rps": lvl.request_throughput_rps,
            "prefix_hit_rate": lvl.telemetry.get("prefix_cache_hit_rate"),
        }[name]


async def benchmark_variant(
    name: str,
    repo: Path,
    questions: list[str],
    target: BenchTarget,
    *,
    concurrency: int = 8,
    max_tokens: int = 64,
    slo_ttft_ms: float = 500.0,
    seed: int = 7,
) -> VariantResult:
    run_ref = uuid.uuid4().hex[:6]
    unique = [f"{q} (ref {run_ref}-{i})" for i, q in enumerate(questions)]
    rendered = render_in_sandbox(repo, unique)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for msgs in rendered:
            f.write(json.dumps({"messages": msgs, "max_tokens": max_tokens}) + "\n")
        path = f.name
    plan = BenchPlan(
        concurrency_levels=[concurrency],
        requests_per_level=len(rendered),
        warmup_requests=0,
        cooldown_s=0,
        prompt_mode=PromptMode.replay,
        replay_path=path,
        length_mode=LengthMode.fixed,
        seed=seed,
        slo=SLO(ttft_p95_ms=slo_ttft_ms),
    )
    spec = WorkloadSpec(name=f"{name}-rendered", source=WorkloadSource.synthetic, synthetic=False)
    result = await run_benchmark(target, spec, plan, sample_gpu=True)
    await asyncio.to_thread(Path(path).unlink, missing_ok=True)
    result.report.notes.append(
        f"Prompts rendered from the {name} revision's own code ({len(rendered)} requests, run ref {run_ref})."
    )
    return VariantResult(name, result.report)


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def compare(
    baseline: Sequence[MetricSource], other: Sequence[MetricSource], policy: GatePolicy
) -> dict[str, Any]:
    """Median-of-runs comparison. A *block* additionally requires the runs not to overlap
    (every run of `other` worse than every run of `baseline`), so run-to-run noise on a
    shared GPU cannot block a change by itself; without separation the verdict is warn."""
    bs = [v for v in (r.metric(policy.metric) for r in baseline) if v is not None]
    os_ = [v for v in (r.metric(policy.metric) for r in other) if v is not None]
    if not bs or not os_:
        return {"verdict": "error", "reason": f"{policy.metric} not measured"}
    b, o = _median(bs), _median(os_)
    change_pct = (o - b) / b * 100
    separated = min(os_) > max(bs)
    if change_pct > policy.block_pct:
        verdict = "block" if separated or len(bs) == 1 else "warn"
    elif change_pct > policy.warn_pct:
        verdict = "warn"
    else:
        verdict = "pass"

    def med(rs: Sequence[MetricSource], name: str) -> float | None:
        vals = [v for v in (r.metric(name) for r in rs) if v is not None]
        return _median(vals) if vals else None

    return {
        "metric": policy.metric,
        "baseline": round(b, 1),
        "value": round(o, 1),
        "change_pct": round(change_pct, 1),
        "verdict": verdict,
        "runs": len(os_),
        "baseline_runs": [round(x, 1) for x in bs],
        "value_runs": [round(x, 1) for x in os_],
        "separated": separated,
        "prefix_hit_rate": (med(baseline, "prefix_hit_rate"), med(other, "prefix_hit_rate")),
        "goodput_rps": (med(baseline, "goodput_rps"), med(other, "goodput_rps")),
    }


def run_gate(
    variants: dict[str, Path],
    questions: list[str],
    target: BenchTarget,
    *,
    repeats: int = 3,
    **kw: Any,
) -> dict[str, list[VariantResult]]:
    """Benchmark revisions sequentially (they share the GPU), interleaving repeats
    (A, B, A, B, ...) so drift in clocks or temperature affects all revisions alike."""

    async def go() -> dict[str, list[VariantResult]]:
        out: dict[str, list[VariantResult]] = {name: [] for name in variants}
        for _ in range(repeats):
            for name, repo in variants.items():
                out[name].append(await benchmark_variant(name, repo, questions, target, **kw))
        return out

    return asyncio.run(go())
