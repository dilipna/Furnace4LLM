"""Write benchmark artifacts: report.json, requests.jsonl, telemetry.jsonl, report.md."""

from __future__ import annotations

import json
from pathlib import Path

from furnace_bench.runner import BenchResult
from furnace_bench.schema import BenchReport, LevelSummary, Percentiles


def _f(v: float | None, digits: int = 1) -> str:
    return "–" if v is None else f"{v:.{digits}f}"


def _pct(p: Percentiles, key: str) -> str:
    v = getattr(p, key)
    ci = getattr(p, f"{key}_ci", None)
    if v is None:
        return "–"
    return f"{v:.1f} [{ci[0]:.1f}, {ci[1]:.1f}]" if ci else f"{v:.1f}"


def render_markdown(report: BenchReport) -> str:
    t, p, e = report.target, report.plan, report.env
    lines = [
        f"# furnace-bench report `{report.run_id}`",
        "",
        f"- **Target:** `{t.adapter.value}` · model `{t.model}` · {t.base_url}"
        + (f" · {t.label}" if t.label else ""),
        f"- **Engine:** {e.engine or '?'} {e.engine_version or ''} · model root `{e.model_revision or '?'}`",
        f"- **Host:** {e.platform} · GPU {e.gpu or 'not sampled'} (driver {e.gpu_driver or '–'})",
        f"- **Workload:** `{report.workload_name}`"
        + (" (**synthetic**)" if report.workload_synthetic else ""),
        f"- **Plan:** {p.arrival.value}, levels {', '.join(f'{x:g}' for x in p.concurrency_levels)}, "
        f"{p.requests_per_level} req/level (+{p.warmup_requests} warmup), {p.repeats} repeat(s), "
        f"length mode `{p.length_mode.value}`, stream={p.stream}, seed {p.seed}",
        f"- **SLO:** TTFT ≤ {_f(p.slo.ttft_p95_ms, 0)} ms · TPOT ≤ {_f(p.slo.tpot_p95_ms, 0)} ms · "
        f"E2E ≤ {_f(p.slo.e2e_p95_ms, 0)} ms (per request)",
        f"- **furnace-bench** {e.furnace_bench_version} · git `{(e.furnace_git_sha or '–')[:10]}` · {e.started_at}",
        "",
        "## Latency (ms; p95/p99 with 95% bootstrap CI)",
        "",
        "| level | rep | ok/n | TTFT p50 | TTFT p95 | TTFT p99 | TPOT p50 | TPOT p95 | E2E p95 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in report.levels:
        lines.append(
            f"| {s.level:g} | {s.repeat} | {s.n_ok}/{s.n} | {_f(s.ttft_ms.p50)} | {_pct(s.ttft_ms, 'p95')} | "
            f"{_pct(s.ttft_ms, 'p99')} | {_f(s.tpot_ms.p50, 2)} | {_f(s.tpot_ms.p95, 2)} | {_pct(s.e2e_ms, 'p95')} |"
        )
    lines += [
        "",
        "## Throughput, goodput, server",
        "",
        "| level | rep | req/s | out tok/s | in tok/s | SLO goodput req/s | goodput % | fail % | prefix-cache hit | KV max | GPU util | tok/chunk |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in report.levels:
        lines.append(_throughput_row(s))
    exposed_gaps = sorted({m for s in report.levels for m in s.not_exposed})
    if exposed_gaps:
        lines += ["", f"_Not exposed by this endpoint/host:_ {', '.join(exposed_gaps)}"]
    if report.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in report.notes]
    lines += [
        "",
        "## Definitions",
        "",
        "- **TTFT**: request send → first chunk carrying generated output (role-only chunks excluded).",
        "- **TPOT**: (E2E − TTFT) / (output tokens − 1), output tokens from server usage.",
        "- **SLO goodput**: successful requests per second that individually met every configured SLO bound, "
        "over the window from first send to last completion.",
        "- **prefix-cache hit**: Δhits / Δqueries of the server's prefix-cache counters over the level window.",
        "",
    ]
    return "\n".join(lines)


def _throughput_row(s: LevelSummary) -> str:
    tel = s.telemetry
    hit = tel.get("prefix_cache_hit_rate")
    kv = tel.get("kv_cache_usage_max")
    gpu = tel.get("gpu_util_pct_mean")
    return (
        f"| {s.level:g} | {s.repeat} | {s.request_throughput_rps:.2f} | {_f(s.output_tok_s)} | {_f(s.input_tok_s)} | "
        f"{_f(s.slo_goodput_rps, 2)} | {_f(None if s.goodput_ratio is None else s.goodput_ratio * 100)} | "
        f"{s.failure_rate * 100:.1f} | {_f(None if hit is None else hit * 100)}{'%' if hit is not None else ''} | "
        f"{_f(None if kv is None else kv * 100)}{'%' if kv is not None else ''} | "
        f"{_f(gpu)}{'%' if gpu is not None else ''} | {_f(s.tokens_per_chunk, 2)} |"
    )


def write_result(result: BenchResult, out_dir: str | Path) -> Path:
    out = Path(out_dir) / result.report.run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(result.report.model_dump_json(indent=2), encoding="utf-8")
    with (out / "requests.jsonl").open("w", encoding="utf-8") as f:
        for r in result.records:
            f.write(r.model_dump_json() + "\n")
    with (out / "telemetry.jsonl").open("w", encoding="utf-8") as f:
        for s in result.telemetry:
            f.write(json.dumps({"t": round(s.t, 4), **s.metrics}) + "\n")
    (out / "report.md").write_text(render_markdown(result.report), encoding="utf-8")
    return out
