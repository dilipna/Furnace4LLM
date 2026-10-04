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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from furnace_bench.runner import run_benchmark
from furnace_bench.schema import BenchPlan, BenchReport, BenchTarget, LengthMode, PromptMode
from furnace_bench.workload_spec import SLO, WorkloadSource, WorkloadSpec

from furnace.guardian.repair.regression import render_in_sandbox


@dataclass
class GatePolicy:
    warn_pct: float = 10.0
    block_pct: float = 25.0
    metric: str = "ttft_p95_ms"


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


def compare(baseline: VariantResult, other: VariantResult, policy: GatePolicy) -> dict[str, Any]:
    b, o = baseline.metric(policy.metric), other.metric(policy.metric)
    if b is None or o is None:
        return {"verdict": "error", "reason": f"{policy.metric} not measured"}
    change_pct = (o - b) / b * 100
    verdict = (
        "block"
        if change_pct > policy.block_pct
        else "warn"
        if change_pct > policy.warn_pct
        else "pass"
    )
    return {
        "metric": policy.metric,
        "baseline": round(b, 1),
        "value": round(o, 1),
        "change_pct": round(change_pct, 1),
        "verdict": verdict,
        "prefix_hit_rate": (baseline.metric("prefix_hit_rate"), other.metric("prefix_hit_rate")),
        "goodput_rps": (baseline.metric("goodput_rps"), other.metric("goodput_rps")),
    }


def run_gate(
    variants: dict[str, Path],
    questions: list[str],
    target: BenchTarget,
    policy: GatePolicy | None = None,
    **kw: Any,
) -> dict[str, VariantResult]:
    """Benchmark several revisions sequentially (never concurrently: they share the GPU)."""

    async def go() -> dict[str, VariantResult]:
        out = {}
        for name, repo in variants.items():
            out[name] = await benchmark_variant(name, repo, questions, target, **kw)
        return out

    return asyncio.run(go())
