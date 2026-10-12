"""Performance gate: benchmark the prompts each revision actually produces.

Prompts are rendered from each revision's own harness inside the sandbox, then
replayed by furnace-bench against the inference endpoint. Every run appends a
unique per-run reference to each question, so the only cacheable sharing between
requests is the prompt prefix the code produces (no request is ever repeated
verbatim, within or across runs). Results are compared against a regression
budget (warn/block thresholds as fractions of the baseline).

The decision statistic and interval are specified in docs/gate-revision.md (frozen before
this code was written): geometric-mean TTFT per run, the run as the unit of analysis, and
a Welch t interval across runs.

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
from furnace.guardian.tdist import t_quantile


@dataclass
class GatePolicy:
    """`warn_pct` is the tolerance: a change is only called a regression when the whole
    two-sided `confidence` interval of the change lies above it. `block_pct` is the smallest
    point change that blocks a merge (given the interval is above the tolerance) and the
    worst case (interval upper bound) a repair candidate may have against the base revision.
    The tolerance is not a bound on point noise: A/A point changes of 13% were observed
    (bench/results/2026-10-12-gate-revision/dev_analysis.md); the interval is what protects
    unchanged code. `confidence` is two-sided: (1 - confidence) / 2 in each tail."""

    warn_pct: float = 10.0
    block_pct: float = 25.0
    metric: str = "ttft_gmean_ms"  # geometric-mean TTFT of a run's successful requests
    confidence: float = 0.90
    min_runs: int = 3  # per side; fewer cannot give a usable interval


class MetricSource(Protocol):
    def metric(self, name: str) -> float | None: ...


@dataclass
class VariantResult:
    name: str
    report: BenchReport
    # Raw per-request TTFT of the successful measured requests (ms), for the interval
    # and for the report; empty when only the summary is known.
    ttft_ms: list[float] = field(default_factory=list)
    position: int = 0  # order of this run inside its repeat (0 = measured first)

    def samples(self, name: str) -> list[float]:
        return self.ttft_ms if name == "ttft_ms" else []

    def metric(self, name: str) -> float | None:
        lvl = self.report.levels[0]
        return {
            "ttft_p95_ms": lvl.ttft_ms.p95,
            "ttft_p50_ms": lvl.ttft_ms.p50,
            "e2e_p95_ms": lvl.e2e_ms.p95,
            "goodput_rps": lvl.slo_goodput_rps,
            "throughput_rps": lvl.request_throughput_rps,
            "prefix_hit_rate": lvl.telemetry.get("prefix_cache_hit_rate"),
            "failure_rate": lvl.failure_rate,
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


MIN_SAMPLES_PER_RUN = 20  # below this a run's TTFT summary is not meaningful
METHOD_WELCH = "run-level Welch t interval on mean log TTFT (geometric mean), {pct}% two-sided"
METHOD_POINT = "point estimate only (no per-request samples); legacy p95 thresholds"
LEGACY_METRIC = "ttft_p95_ms"


MAX_EXTRA_FAILURE_RATE = 0.01  # more failed requests than the baseline beyond this: BLOCK


def _failure_rate(rs: Sequence[MetricSource]) -> float | None:
    """Mean failed-request share across runs, or None if the source does not report it."""
    vals = []
    for r in rs:
        try:
            v = r.metric("failure_rate")
        except KeyError:
            return None
        if v is None:
            return None
        vals.append(v)
    return sum(vals) / len(vals) if vals else None


def _run_logs(rs: Sequence[MetricSource], percentile: float | None = None) -> list[float] | None:
    """One number per run: the mean of log TTFT, or the log of its `percentile`-th percentile.

    None if any run lacks per-request samples. A run is the unit of analysis; its requests
    are not independent (closed-loop waves share a scheduler step) so they are never
    resampled, only summarized."""
    out: list[float] = []
    for r in rs:
        get = getattr(r, "samples", None)
        xs = np.asarray(get("ttft_ms") if get else [], dtype=float)
        if xs.size < MIN_SAMPLES_PER_RUN or not np.all(xs > 0):
            return None
        out.append(
            float(np.log(xs).mean())
            if percentile is None
            else float(np.log(np.percentile(xs, percentile)))
        )
    return out or None


def welch_change_ci(
    base_logs: Sequence[float], other_logs: Sequence[float], confidence: float
) -> tuple[float, float, float]:
    """(change, low, high) in percent of exp(mean(other) - mean(base)) - 1, with a Welch
    (unequal variance) t interval, Satterthwaite degrees of freedom, two-sided."""
    x, y = np.asarray(base_logs, dtype=float), np.asarray(other_logs, dtype=float)
    va, vb = x.var(ddof=1) / x.size, y.var(ddof=1) / y.size
    se = float(np.sqrt(va + vb))
    d = float(y.mean() - x.mean())
    if se == 0.0:
        lo = hi = d
    else:
        df = (va + vb) ** 2 / (va**2 / (x.size - 1) + vb**2 / (y.size - 1))
        q = t_quantile(1 - (1 - confidence) / 2, df)
        lo, hi = d - q * se, d + q * se
    return float(np.expm1(d) * 100), float(np.expm1(lo) * 100), float(np.expm1(hi) * 100)


def _verdict(lo: float, hi: float, change: float, policy: GatePolicy) -> str:
    if hi <= policy.warn_pct:
        return "pass"
    if lo > policy.warn_pct:
        return "block" if change > policy.block_pct else "warn"
    return "inconclusive"


def _med(rs: Sequence[MetricSource], name: str) -> float | None:
    vals = [v for v in (r.metric(name) for r in rs) if v is not None]
    return _median(vals) if vals else None


def _compare_welch(
    baseline: Sequence[MetricSource],
    other: Sequence[MetricSource],
    b_logs: list[float],
    o_logs: list[float],
    policy: GatePolicy,
) -> dict[str, Any]:
    gm_b, gm_o = float(np.exp(np.mean(b_logs))), float(np.exp(np.mean(o_logs)))
    base_runs = [round(float(np.exp(v)), 1) for v in b_logs]
    value_runs = [round(float(np.exp(v)), 1) for v in o_logs]
    out: dict[str, Any] = {
        "metric": policy.metric,
        "baseline": round(gm_b, 1),
        "value": round(gm_o, 1),
        "tolerance_pct": policy.warn_pct,
        "block_pct": policy.block_pct,
        "confidence": policy.confidence,
        "runs": len(o_logs),
        "baseline_runs": base_runs,
        "value_runs": value_runs,
        "separated": min(value_runs) > max(base_runs),
        "method": METHOD_WELCH.format(pct=round(policy.confidence * 100)),
    }
    if min(len(b_logs), len(o_logs)) < policy.min_runs:
        out |= {
            "change_pct": round((gm_o - gm_b) / gm_b * 100, 1),
            "ci_pct": None,
            "verdict": "inconclusive",
            "reason": (
                f"{len(b_logs)} vs {len(o_logs)} runs; at least {policy.min_runs} per side "
                "are needed for an interval"
            ),
        }
        return out
    change, lo, hi = welch_change_ci(b_logs, o_logs, policy.confidence)
    out |= {
        "change_pct": round(change, 1),
        "ci_pct": [round(lo, 1), round(hi, 1)],
        "verdict": _verdict(lo, hi, change, policy),
    }
    bp, op = _run_logs(baseline, 95), _run_logs(other, 95)
    if bp and op:
        p_change, p_lo, p_hi = welch_change_ci(bp, op, policy.confidence)
        out["p95_advisory"] = {
            "baseline": round(float(np.exp(np.mean(bp))), 1),
            "value": round(float(np.exp(np.mean(op))), 1),
            "change_pct": round(p_change, 1),
            "ci_pct": [round(p_lo, 1), round(p_hi, 1)],
            "note": "reported, not used for the verdict: a p95 over a few dozen requests is "
            "too noisy to confirm a 10% tolerance",
        }
    out["samples_ms"] = {
        "baseline": [[round(float(x), 2) for x in r.samples("ttft_ms")] for r in baseline],  # type: ignore[attr-defined]
        "value": [[round(float(x), 2) for x in r.samples("ttft_ms")] for r in other],  # type: ignore[attr-defined]
    }
    return out


def _compare_point(
    baseline: Sequence[MetricSource], other: Sequence[MetricSource], policy: GatePolicy
) -> dict[str, Any]:
    """Summaries only (no per-request samples): the earlier point rule on p95, labeled."""
    bs = [v for v in (r.metric(LEGACY_METRIC) for r in baseline) if v is not None]
    os_ = [v for v in (r.metric(LEGACY_METRIC) for r in other) if v is not None]
    if not bs or not os_:
        return {"verdict": "error", "reason": f"{LEGACY_METRIC} not measured"}
    b, o = _median(bs), _median(os_)
    change = (o - b) / b * 100
    separated = min(os_) > max(bs)
    if change > policy.block_pct:
        verdict = "block" if separated or len(bs) == 1 else "warn"
    elif change > policy.warn_pct:
        verdict = "warn"
    else:
        verdict = "pass"
    return {
        "metric": LEGACY_METRIC,
        "baseline": round(b, 1),
        "value": round(o, 1),
        "change_pct": round(change, 1),
        "ci_pct": None,
        "verdict": verdict,
        "method": METHOD_POINT,
        "tolerance_pct": policy.warn_pct,
        "block_pct": policy.block_pct,
        "runs": len(os_),
        "baseline_runs": [round(x, 1) for x in bs],
        "value_runs": [round(x, 1) for x in os_],
        "separated": separated,
    }


def compare(
    baseline: Sequence[MetricSource], other: Sequence[MetricSource], policy: GatePolicy
) -> dict[str, Any]:
    """Compare `other` against `baseline`.

    With per-request samples (the real gate path), the verdict comes from the two-sided
    `policy.confidence` Welch interval of the change in geometric-mean TTFT, against the
    tolerance (warn_pct) and block_pct:
      pass          the interval lies at or below the tolerance (a larger regression is ruled out);
      block         the interval lies above the tolerance and the point change exceeds block_pct;
      warn          the interval lies above the tolerance, the point change is modest;
      inconclusive  the interval straddles the tolerance, or fewer than `min_runs` runs per
                    side: the data support neither answer, and it is never reported as a pass.
    The p95 is reported (`p95_advisory`) with its own interval but does not decide.
    Without samples (summaries only) the earlier point rule on p95 is used and labeled."""
    b_logs, o_logs = _run_logs(baseline), _run_logs(other)
    if b_logs is not None and o_logs is not None:
        out = _compare_welch(baseline, other, b_logs, o_logs, policy)
    else:
        out = _compare_point(baseline, other, policy)
        if out["verdict"] == "error":
            return out

    # Latency is measured over successful requests only, so a revision whose requests fail
    # (context overflow, server errors) could look faster. More failures than the baseline
    # (beyond one point, for a transient error) block regardless of latency.
    b_fail, o_fail = _failure_rate(baseline), _failure_rate(other)
    if b_fail is not None and o_fail is not None and o_fail - b_fail > MAX_EXTRA_FAILURE_RATE:
        out["verdict"] = "block"
        out["reason"] = (
            f"{o_fail:.0%} of requests failed vs {b_fail:.0%} on the baseline; latency over the "
            "successful requests alone would be misleading"
        )
    out |= {
        "prefix_hit_rate": (_med(baseline, "prefix_hit_rate"), _med(other, "prefix_hit_rate")),
        "goodput_rps": (_med(baseline, "goodput_rps"), _med(other, "goodput_rps")),
        "failure_rate": (
            None if b_fail is None else round(b_fail, 4),
            None if o_fail is None else round(o_fail, 4),
        ),
    }
    return out


def describe(c: dict[str, Any]) -> str:
    """One line for logs, check runs and PR bodies."""
    if c.get("verdict") == "error":
        return f"not measured: {c.get('reason')}"
    ci = c.get("ci_pct")
    conf = round(c.get("confidence", 0.95) * 100)
    ci_txt = f", {conf}% interval {ci[0]:+.1f}% to {ci[1]:+.1f}%" if ci else ""
    line = (
        f"{c['baseline']} -> {c['value']} ms ({c['change_pct']:+.1f}%{ci_txt}; "
        f"{c['verdict'].upper()} at tolerance {c['tolerance_pct']:g}%)"
    )
    return f"{line}; {c['reason']}" if c.get("reason") else line


def accept_repair(
    head_vs_base: dict[str, Any],
    cand_vs_base: dict[str, Any],
    cand_vs_head: dict[str, Any],
    policy: GatePolicy,
) -> tuple[bool, list[str]]:
    """The perf gate for a repair candidate, kept separate from its functional tests.

    Accept only if (1) the candidate is faster than the PR head (the interval's upper bound
    is below zero: a 95% one-sided limit for a 90% two-sided interval) and (2) its worst case
    against the base revision (the interval's upper bound) stays below block_pct (it is not
    a new regression of blocking size). Whether it is within the noise tolerance of base is reported, not assumed:
    staying inside a tolerance band is not evidence of an improvement."""
    if "error" in (head_vs_base.get("verdict"), cand_vs_base.get("verdict")):
        return False, ["the benchmark measured nothing; a candidate is never accepted unmeasured"]
    if cand_vs_base.get("reason") and cand_vs_base.get("verdict") == "block":
        return False, [f"candidate blocked: {cand_vs_base['reason']}"]
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
        f"{cand_vs_head['change_pct']:+.1f}% ({round(policy.confidence * 100)}% interval "
        f"{ci_h[0]:+.1f}% to {ci_h[1]:+.1f}%)"
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
