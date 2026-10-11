"""Performance gate: benchmark the prompts each revision actually produces.

Prompts are rendered from each revision's own harness inside the sandbox, then
replayed by furnace-bench against the inference endpoint. Every run appends a
unique per-run reference to each question, so the only cacheable sharing between
requests is the prompt prefix the code produces (no request is ever repeated
verbatim, within or across runs). Results are compared against a regression
budget (warn/block thresholds as fractions of the baseline).

Each measured run is preceded by one unmeasured warmup wave (as many distinct requests as
the concurrency) rendered from the same revision. Without it, the first wave after the GPU
sat idle (while the next revision's prompts were rendered) took ~200 ms instead of ~65 ms,
and with 34 requests per run that wave alone set the p95: an A/A calibration on 2026-10-09
found medians of identical revisions differing by up to 60% (bench/results/2026-10-09/
gate_noise_no_warmup.md).
"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from furnace_bench.runner import run_benchmark
from furnace_bench.schema import BenchPlan, BenchReport, BenchTarget, LengthMode, PromptMode
from furnace_bench.workload_spec import SLO, WorkloadSource, WorkloadSpec

from furnace.guardian.repair.regression import render_in_sandbox


@dataclass
class GatePolicy:
    """`warn_pct` is the tolerance: the largest change treated as measurement noise. It must
    be at least the A/A calibration's worst case (9.7% on 2026-10-09, gate_noise.md); a change
    is only called a regression when its whole 95% interval lies above it. `block_pct` is
    the smallest regression that blocks a merge, and the worst case (interval upper bound)
    a repair candidate may have against the base revision."""

    warn_pct: float = 10.0
    block_pct: float = 25.0
    metric: str = "ttft_p95_ms"
    confidence: float = 0.95
    n_boot: int = 2000
    seed: int = 0


class MetricSource(Protocol):
    def metric(self, name: str) -> float | None: ...


@dataclass
class VariantResult:
    name: str
    report: BenchReport
    # Raw per-request TTFT of the successful measured requests (ms), for the bootstrap
    # interval and for the report; empty when only the summary is known.
    ttft_ms: list[float] = field(default_factory=list)
    position: int = 0  # order of this run inside its repeat (0 = measured first)

    def samples(self, name: str) -> list[float]:
        return self.ttft_ms if name.startswith("ttft_") else []

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
    warmup: int | None = None,
    request_multiplier: int = 1,
) -> VariantResult:
    """`request_multiplier` > 1 sends each question that many times per run (each with its
    own reference, so never verbatim twice) to narrow the interval; the repeated question
    text adds some prefix sharing to both sides alike."""
    run_ref = uuid.uuid4().hex[:6]
    unique = [f"{q} (ref {run_ref}-{i})" for i, q in enumerate(questions * request_multiplier)]
    n_warm = concurrency if warmup is None else warmup
    warm_q = [f"{questions[i % len(questions)]} (warmup {run_ref}-{i})" for i in range(n_warm)]
    rendered_all = render_in_sandbox(repo, unique + warm_q)
    rendered, warm = rendered_all[: len(unique)], rendered_all[len(unique) :]
    spec = WorkloadSpec(name=f"{name}-rendered", source=WorkloadSource.synthetic, synthetic=False)
    if warm:  # distinct prompts, unmeasured: wakes the GPU and warms this revision's prefix
        await _run_rendered(warm, target, spec, concurrency, max_tokens, slo_ttft_ms, seed, False)
    result = await _run_rendered(
        rendered, target, spec, concurrency, max_tokens, slo_ttft_ms, seed, True
    )
    result.report.notes.append(
        f"Prompts rendered from the {name} revision's own code ({len(rendered)} requests, "
        f"run ref {run_ref}; {len(warm)} distinct warmup requests before, not measured)."
    )
    ttft = [r.ttft_ms for r in result.records if r.ok and r.ttft_ms is not None]
    return VariantResult(name, result.report, ttft_ms=ttft)


async def _run_rendered(
    rendered: list[list[dict]],
    target: BenchTarget,
    spec: WorkloadSpec,
    concurrency: int,
    max_tokens: int,
    slo_ttft_ms: float,
    seed: int,
    sample_gpu: bool,
) -> Any:
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
    result = await run_benchmark(target, spec, plan, sample_gpu=sample_gpu)
    await asyncio.to_thread(Path(path).unlink, missing_ok=True)
    return result


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


MIN_SAMPLES_PER_RUN = 20  # below this a bootstrap of a tail percentile is not meaningful
METHOD_BOOTSTRAP = "hierarchical bootstrap (runs, then requests within runs), 95% interval"
METHOD_POINT = "point estimate only (no per-request samples); legacy thresholds"


def _percentile_of(metric: str) -> float | None:
    m = re.fullmatch(r"ttft_p(\d+)_ms", metric)
    return float(m.group(1)) if m else None


def _run_samples(rs: Sequence[MetricSource], metric: str) -> list[np.ndarray] | None:
    out = []
    for r in rs:
        get = getattr(r, "samples", None)
        xs = get(metric) if get else []
        if len(xs) < MIN_SAMPLES_PER_RUN:
            return None
        out.append(np.asarray(xs, dtype=float))
    return out or None


def bootstrap_change_ci(
    base_runs: list[np.ndarray],
    other_runs: list[np.ndarray],
    q: float,
    *,
    n_boot: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Percentile interval for the % change of the median-of-runs q-th percentile.

    Hierarchical: each replicate resamples whole runs with replacement (between-run noise:
    clocks, scheduling, cache state), then the requests inside each chosen run (within-run
    noise), recomputes each run's q-th percentile (numpy linear, as furnace-bench does) and
    the median across runs. With 3 runs per side the run level has few distinct resamples,
    so the interval is coarse; that coarseness is real uncertainty, not an artifact."""
    rng = np.random.default_rng(seed)

    def replicates(runs: list[np.ndarray]) -> np.ndarray:
        k = len(runs)
        per_run = np.stack(  # (k, n_boot): bootstrap percentiles of each run
            [
                np.percentile(a[rng.integers(0, a.size, size=(n_boot, a.size))], q, axis=1)
                for a in runs
            ]
        )
        which = rng.integers(0, k, size=(n_boot, k))  # runs drawn with replacement
        col = rng.integers(0, n_boot, size=(n_boot, k))  # an independent resample of each
        return np.median(per_run[which, col], axis=1)

    b, o = replicates(base_runs), replicates(other_runs)
    change = (o - b) / b * 100
    tail = (1 - confidence) / 2 * 100
    return float(np.percentile(change, tail)), float(np.percentile(change, 100 - tail))


def compare(
    baseline: Sequence[MetricSource], other: Sequence[MetricSource], policy: GatePolicy
) -> dict[str, Any]:
    """Compare `other` against `baseline` on the median across runs of `policy.metric`.

    With per-request samples (the real gate path) the verdict comes from the 95% interval
    of the change, against the tolerance (warn_pct) and the block threshold:
      pass          the interval lies at or below the tolerance (no regression beyond noise);
      block         the interval lies above the tolerance, the point change exceeds
                    block_pct, and every `other` run is slower than every baseline run
                    (with 3 runs a side, a 1-in-20 event under no difference);
      warn          a regression beyond the tolerance, but small or with overlapping runs;
      inconclusive  the interval straddles the tolerance: the noise does not support either
                    answer, and it is reported as such, never as a pass.
    Without samples (summaries only) the earlier point rule is used and labeled."""
    bs = [v for v in (r.metric(policy.metric) for r in baseline) if v is not None]
    os_ = [v for v in (r.metric(policy.metric) for r in other) if v is not None]
    if not bs or not os_:
        return {"verdict": "error", "reason": f"{policy.metric} not measured"}
    b, o = _median(bs), _median(os_)
    change_pct = (o - b) / b * 100
    separated = min(os_) > max(bs)
    q = _percentile_of(policy.metric)
    b_samples = _run_samples(baseline, policy.metric) if q is not None else None
    o_samples = _run_samples(other, policy.metric) if q is not None else None
    ci: tuple[float, float] | None = None
    if q is not None and b_samples and o_samples:
        ci = bootstrap_change_ci(
            b_samples,
            o_samples,
            q,
            n_boot=policy.n_boot,
            seed=policy.seed,
            confidence=policy.confidence,
        )
        lo, hi = ci
        if hi <= policy.warn_pct:
            verdict = "pass"
        elif lo > policy.warn_pct:
            big = change_pct > policy.block_pct
            verdict = "block" if big and (separated or len(bs) == 1) else "warn"
        else:
            verdict = "inconclusive"
        method = METHOD_BOOTSTRAP
    else:
        if change_pct > policy.block_pct:
            verdict = "block" if separated or len(bs) == 1 else "warn"
        elif change_pct > policy.warn_pct:
            verdict = "warn"
        else:
            verdict = "pass"
        method = METHOD_POINT

    def med(rs: Sequence[MetricSource], name: str) -> float | None:
        vals = [v for v in (r.metric(name) for r in rs) if v is not None]
        return _median(vals) if vals else None

    out: dict[str, Any] = {
        "metric": policy.metric,
        "baseline": round(b, 1),
        "value": round(o, 1),
        "change_pct": round(change_pct, 1),
        "ci_pct": [round(ci[0], 1), round(ci[1], 1)] if ci else None,
        "verdict": verdict,
        "method": method,
        "tolerance_pct": policy.warn_pct,
        "block_pct": policy.block_pct,
        "runs": len(os_),
        "baseline_runs": [round(x, 1) for x in bs],
        "value_runs": [round(x, 1) for x in os_],
        "separated": separated,
        "prefix_hit_rate": (med(baseline, "prefix_hit_rate"), med(other, "prefix_hit_rate")),
        "goodput_rps": (med(baseline, "goodput_rps"), med(other, "goodput_rps")),
    }
    if b_samples and o_samples:
        out["samples_ms"] = {
            "baseline": [[round(float(x), 2) for x in a] for a in b_samples],
            "value": [[round(float(x), 2) for x in a] for a in o_samples],
        }
    return out


def describe(c: dict[str, Any]) -> str:
    """One line for logs, check runs and PR bodies."""
    if c.get("verdict") == "error":
        return f"not measured: {c.get('reason')}"
    ci = c.get("ci_pct")
    ci_txt = f", 95% CI {ci[0]:+.1f}% to {ci[1]:+.1f}%" if ci else ""
    return (
        f"{c['baseline']} -> {c['value']} ms ({c['change_pct']:+.1f}%{ci_txt}; "
        f"{c['verdict'].upper()} at tolerance {c['tolerance_pct']:g}%)"
    )


def accept_repair(
    head_vs_base: dict[str, Any],
    cand_vs_base: dict[str, Any],
    cand_vs_head: dict[str, Any],
    policy: GatePolicy,
) -> tuple[bool, list[str]]:
    """The perf gate for a repair candidate, kept separate from its functional tests.

    Accept only if (1) the candidate is faster than the PR head with 95% confidence (it
    actually repairs the regression) and (2) its worst case against the base revision (the
    interval's upper bound) stays below block_pct (it is not a new regression of blocking
    size). Whether it is within the noise tolerance of base is reported, not assumed:
    staying inside a tolerance band is not evidence of an improvement."""
    if "error" in (head_vs_base.get("verdict"), cand_vs_base.get("verdict")):
        return False, ["the benchmark measured nothing; a candidate is never accepted unmeasured"]
    ci_h, ci_b = cand_vs_head.get("ci_pct"), cand_vs_base.get("ci_pct")
    if ci_h is None or ci_b is None:  # summaries only: the earlier rule, labeled
        ok = cand_vs_base["verdict"] in ("pass", "warn")
        return ok, [
            f"point rule (no per-request samples): candidate vs base {describe(cand_vs_base)}"
        ]
    reasons = []
    fixes = ci_h[1] < 0
    reasons.append(
        f"{'faster' if fixes else 'NOT shown faster'} than the PR head: change "
        f"{cand_vs_head['change_pct']:+.1f}% (95% CI {ci_h[0]:+.1f}% to {ci_h[1]:+.1f}%)"
    )
    bounded = ci_b[1] < policy.block_pct
    reasons.append(
        f"worst case vs base {ci_b[1]:+.1f}% {'<' if bounded else '>='} block threshold "
        f"{policy.block_pct:g}% (change {cand_vs_base['change_pct']:+.1f}%)"
    )
    reasons.append(
        f"within the {policy.warn_pct:g}% noise tolerance of base: "
        + ("shown (whole interval inside)" if ci_b[1] <= policy.warn_pct else "NOT shown")
    )
    return fixes and bounded, reasons


def repair_perf_check(res: dict[str, list[VariantResult]], policy: GatePolicy) -> dict[str, Any]:
    """Gate a repair from one interleaved run of base, PR head and candidate."""
    hv = compare(res["base"], res["pr_head"], policy)
    cv = compare(res["base"], res["candidate"], policy)
    ch = compare(res["pr_head"], res["candidate"], policy)
    ok, reasons = accept_repair(hv, cv, ch, policy)
    return {
        "head_vs_base": hv,
        "candidate_vs_base": cv,
        "candidate_vs_head": ch,
        "within_budget": ok,
        "reasons": reasons,
        "summary": f"p95 TTFT base {hv.get('baseline')} | PR {describe(hv)} | repair {describe(cv)}",
    }


def run_order(names: list[str], repeat: int) -> list[str]:
    """Rotate the order each repeat (a Latin square: A,B,C / B,C,A / C,A,B), so no revision is
    always measured first; the A/A study found the first-measured side biased."""
    k = repeat % len(names)
    return names[k:] + names[:k]


def run_gate(
    variants: dict[str, Path],
    questions: list[str],
    target: BenchTarget,
    *,
    repeats: int = 3,
    **kw: Any,
) -> dict[str, list[VariantResult]]:
    """Benchmark revisions sequentially (they share the GPU), interleaving repeats and
    rotating their order (run_order) so drift in clocks or temperature and any first-run
    effect fall on all revisions alike."""

    async def go() -> dict[str, list[VariantResult]]:
        out: dict[str, list[VariantResult]] = {name: [] for name in variants}
        for r in range(repeats):
            for pos, name in enumerate(run_order(list(variants), r)):
                v = await benchmark_variant(name, variants[name], questions, target, **kw)
                v.position = pos
                out[name].append(v)
        return out

    return asyncio.run(go())
