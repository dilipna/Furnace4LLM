"""FurnaceBench RQ4: inference sweep on workload W1 (the F1 trace fingerprint).

Matrix: prefix caching {on, off} x max-num-seqs {8, 32, 128} on one vLLM model, closed
loop at concurrency 1..16, `--repeats` repetitions. Runs are interleaved repeat-major
(every config once, then again, with the config order rotated each repeat) so slow drift
in GPU clocks or temperature spreads across configs instead of biasing one. Within a
repeat every config gets the same seed, i.e. the same request sequence (paired design).

Each config is a fresh container (`furnace-rq4-lab`, port 8101). The compose `vllm`
service is stopped during the sweep (one 4 GB GPU) and restarted afterwards. A config
that fails to launch is recorded as a result, not skipped silently.

  uv run poe bench-rq4                      # full sweep, then summary
  uv run poe bench-rq4 --summarize-only     # rebuild rq4.json / rq4.md from runs/
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from common import (
    ROOT,
    W1,
    manifest,
    md_table,
    read_json,
    results_dir,
    write_json,
)
from furnace_bench.report.writer import write_result
from furnace_bench.runner import run_benchmark
from furnace_bench.schema import AdapterName, BenchPlan, BenchTarget, LengthMode
from furnace_bench.workload_spec import SLO, WorkloadSpec

IMAGE = "vllm/vllm-openai:latest"
CONTAINER = "furnace-rq4-lab"
PORT = 8101
HF_HOME = Path.home() / ".cache" / "huggingface"
CONFIGS = [
    {"name": f"pc-{'on' if pc else 'off'}_seqs-{s}", "prefix_cache": pc, "max_num_seqs": s}
    for pc in (True, False)
    for s in (8, 32, 128)
]
SLO_TTFT_MS = 500.0


def sh(*cmd: str, check: bool = False, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        list(cmd), capture_output=True, text=True, timeout=timeout, check=check, cwd=ROOT
    )


def image_digest() -> str | None:
    r = sh("docker", "image", "inspect", IMAGE, "--format", "{{index .RepoDigests 0}}")
    return r.stdout.strip() or None


def launch(cfg: dict[str, Any], model: str, gpu_util: float) -> tuple[bool, str]:
    sh("docker", "rm", "-f", CONTAINER)
    args = [
        "docker",
        "run",
        "-d",
        "--name",
        CONTAINER,
        "--gpus",
        "all",
        "--ipc",
        "host",
        "-p",
        f"{PORT}:8000",
        "-v",
        f"{HF_HOME.as_posix()}:/root/.cache/huggingface",
        IMAGE,
        f"--model={model}",
        "--served-model-name=lab",
        f"--gpu-memory-utilization={gpu_util}",
        "--max-model-len=4096",
        f"--max-num-seqs={cfg['max_num_seqs']}",
        "--enable-prefix-caching" if cfg["prefix_cache"] else "--no-enable-prefix-caching",
    ]
    r = sh(*args)
    if r.returncode != 0:
        return False, r.stderr[-800:]
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"http://localhost:{PORT}/v1/models", timeout=3).status_code == 200:
                return True, ""
        except httpx.HTTPError:
            pass
        state = sh("docker", "inspect", CONTAINER, "--format", "{{.State.Running}}").stdout
        if state.strip() != "true":
            break
        time.sleep(3)
    logs = sh("docker", "logs", "--tail", "40", CONTAINER)
    return False, (logs.stdout + logs.stderr)[-2000:]


def run_one(cfg: dict[str, Any], rep: int, args: argparse.Namespace, out: Path) -> dict[str, Any]:
    spec = WorkloadSpec.model_validate(yaml.safe_load(W1.read_text(encoding="utf-8")))
    target = BenchTarget(
        adapter=AdapterName.vllm,
        base_url=f"http://localhost:{PORT}/v1",
        model="lab",
        metrics_url=f"http://localhost:{PORT}/metrics",
        label=cfg["name"],
        server_flags={
            "model": args.model,
            "enable-prefix-caching": cfg["prefix_cache"],
            "max-num-seqs": cfg["max_num_seqs"],
            "gpu-memory-utilization": args.gpu_util,
            "max-model-len": 4096,
            "image": IMAGE,
        },
    )
    plan = BenchPlan(
        concurrency_levels=[float(x) for x in args.levels.split(",")],
        requests_per_level=args.n,
        warmup_requests=8,
        length_mode=LengthMode.fixed,
        seed=1234 + rep,
        slo=SLO(ttft_p95_ms=SLO_TTFT_MS),
    )
    res = asyncio.run(run_benchmark(target, spec, plan, progress=lambda m: print("   ", m)))
    res.report.notes.append(f"rq4 config={cfg['name']} repeat={rep}")
    path = write_result(res, out)
    return {"config": cfg["name"], "repeat": rep, "run_dir": path.relative_to(ROOT).as_posix()}


def sweep(args: argparse.Namespace) -> None:
    out = results_dir("rq4")
    index_path = out / "runs.json"
    index: dict[str, Any] = (
        read_json(index_path)
        if index_path.exists()
        else {"manifest": manifest(image_digest=image_digest(), model=args.model), "runs": []}
    )
    done = {(r["config"], r["repeat"]) for r in index["runs"]}
    configs = [c for c in CONFIGS if not args.configs or c["name"] in args.configs.split(",")]
    sh("docker", "compose", "stop", "vllm", timeout=180)
    try:
        for rep in range(args.repeats):
            k = rep % len(configs)
            for cfg in configs[k:] + configs[:k]:
                if (cfg["name"], rep) in done:
                    continue
                print(f"== {cfg['name']} repeat {rep}: launching", flush=True)
                t0 = time.monotonic()
                ok, log = launch(cfg, args.model, args.gpu_util)
                if not ok:
                    print(f"   launch FAILED\n{log}", flush=True)
                    entry: dict[str, Any] = {
                        "config": cfg["name"],
                        "repeat": rep,
                        "launch_failed": True,
                        "log_tail": log,
                    }
                else:
                    print(f"   ready in {time.monotonic() - t0:.0f}s", flush=True)
                    time.sleep(args.settle_s)  # let post-load compilation and clocks settle
                    entry = run_one(cfg, rep, args, out / "runs")
                index["runs"].append(entry)
                write_json(index_path, index)
    finally:
        sh("docker", "rm", "-f", CONTAINER)
        sh("docker", "compose", "--profile", "gpu", "up", "-d", "vllm", timeout=180)


# ------------------------------------------------------------------------------ summary


def _agg(xs: list[float]) -> dict[str, float | None]:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"median": None, "min": None, "max": None, "n": 0}
    return {"median": statistics.median(xs), "min": min(xs), "max": max(xs), "n": len(xs)}


METRICS = {
    "ttft_p50_ms": lambda lv: lv["ttft_ms"]["p50"],
    "ttft_p95_ms": lambda lv: lv["ttft_ms"]["p95"],
    "ttft_p99_ms": lambda lv: lv["ttft_ms"]["p99"],
    "tpot_p50_ms": lambda lv: lv["tpot_ms"]["p50"],
    "e2e_p95_ms": lambda lv: lv["e2e_ms"]["p95"],
    "throughput_rps": lambda lv: lv["request_throughput_rps"],
    "output_tok_s": lambda lv: lv["output_tok_s"],
    "goodput_rps": lambda lv: lv["slo_goodput_rps"],
    "failure_rate": lambda lv: lv["failure_rate"],
    "prefix_hit_rate": lambda lv: lv["telemetry"].get("prefix_cache_hit_rate"),
    "waiting_max": lambda lv: lv["telemetry"].get("waiting_max"),
    "gpu_temp_c_max": lambda lv: lv["telemetry"].get("gpu_temp_c_max"),
}


def summarize() -> dict[str, Any]:
    out = results_dir("rq4")
    index = read_json(out / "runs.json")
    spec = yaml.safe_load(W1.read_text(encoding="utf-8"))
    shared = sum(g["tokens"] * g["share"] for g in spec["prefix"]["groups"])
    expected_hit = shared / spec["input_tokens"]["mean"]

    per: dict[tuple[str, float], dict[str, list[Any]]] = {}
    failed = [r for r in index["runs"] if r.get("launch_failed")]
    env = None
    for r in index["runs"]:
        if r.get("launch_failed"):
            continue
        rep = read_json(ROOT / r["run_dir"] / "report.json")
        env = env or rep["env"]
        for lv in rep["levels"]:
            slot = per.setdefault((r["config"], lv["level"]), {m: [] for m in METRICS})
            slot.setdefault("_repeats", []).append(r["repeat"])
            for m, f in METRICS.items():
                slot[m].append(f(lv))
    rows = []
    for (cfg, level), vals in sorted(per.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        rows.append(
            {
                "config": cfg,
                "level": level,
                "repeats": vals["_repeats"],
                **{m: _agg(vals[m]) for m in METRICS},
                "raw": {m: vals[m] for m in METRICS},
            }
        )

    # Paired prefix-cache effect: same max-num-seqs, same repeat (same seed), on vs off.
    effects = []
    for s in sorted({c["max_num_seqs"] for c in CONFIGS}):
        on, off = f"pc-on_seqs-{s}", f"pc-off_seqs-{s}"
        for level in sorted({lv for (_, lv) in per}):
            a, b = per.get((on, level)), per.get((off, level))
            if not a or not b:
                continue
            pairs = {
                rp: (x, y)
                for rp, x in zip(a["_repeats"], a["ttft_p95_ms"], strict=True)
                for rq, y in zip(b["_repeats"], b["ttft_p95_ms"], strict=True)
                if rp == rq
            }
            gp = {
                rp: (x, y)
                for rp, x in zip(a["_repeats"], a["goodput_rps"], strict=True)
                for rq, y in zip(b["_repeats"], b["goodput_rps"], strict=True)
                if rp == rq
            }
            d_ttft = [(off_v - on_v) / on_v * 100 for on_v, off_v in pairs.values() if on_v]
            d_good = [on_v - off_v for on_v, off_v in gp.values() if on_v is not None]
            effects.append(
                {
                    "max_num_seqs": s,
                    "level": level,
                    "n_pairs": len(pairs),
                    "ttft_p95_off_vs_on_pct": _agg(d_ttft),
                    "goodput_on_minus_off_rps": _agg(d_good),
                    "consistent_sign": bool(d_ttft)
                    and (all(d > 0 for d in d_ttft) or all(d < 0 for d in d_ttft)),
                }
            )
    summary = {
        "manifest": index["manifest"],
        "engine": env,
        "workload": {
            "file": W1.relative_to(ROOT).as_posix(),
            "input_tokens_mean": spec["input_tokens"]["mean"],
            "shared_prefix_tokens": shared,
            "expected_prefix_hit_rate": expected_hit,
            "trace_reuse_ratio": spec["prefix"]["reuse_ratio_infinite"],
        },
        "slo_ttft_p95_ms": SLO_TTFT_MS,
        "rows": rows,
        "prefix_effect": effects,
        "launch_failures": failed,
    }
    write_json(out / "rq4.json", summary)
    (out / "rq4.md").write_text(render(summary), encoding="utf-8")
    return summary


def _rng(a: dict[str, float | None], nd: int = 0, scale: float = 1.0) -> str:
    if a["median"] is None:
        return "–"
    med, lo, hi = (a[k] * scale for k in ("median", "min", "max"))  # type: ignore[operator]
    return f"{med:,.{nd}f} [{lo:,.{nd}f}, {hi:,.{nd}f}]"


def render(s: dict[str, Any]) -> str:
    m, e = s["manifest"], s["engine"] or {}
    wl = s["workload"]
    lines = [
        "# RQ4: inference sweep on W1 (F1 trace fingerprint)",
        "",
        f"Hardware: {m.get('gpu')} ({m.get('memory_mb')} MB), driver {m.get('driver')}. "
        f"Engine: {e.get('engine')} {e.get('engine_version')}, image `{m.get('image_digest')}`, "
        f"model {m.get('model')}. Furnace commit `{(m.get('git') or {}).get('sha')}`.",
        "",
        f"Workload: `{wl['file']}`, mean {wl['input_tokens_mean']:.0f} input tokens of which "
        f"{wl['shared_prefix_tokens']:.0f} are a shared system prefix; output lengths sampled from "
        "the trace distribution (fixed per request, `ignore_eos`). Closed loop, 60 measured + 8 "
        f"warmup requests per level, SLO TTFT <= {s['slo_ttft_p95_ms']:.0f} ms.",
        "",
        "Cells: median across repeats [min, max]. Each repeat is a fresh server launch.",
        "",
        "## TTFT p95 (ms) by config and concurrency",
        "",
    ]
    configs = sorted({r["config"] for r in s["rows"]})
    levels = sorted({r["level"] for r in s["rows"]})
    by = {(r["config"], r["level"]): r for r in s["rows"]}

    def table(metric: str, nd: int = 0, scale: float = 1.0) -> str:
        return md_table(
            ["config", *[f"c={lv:g}" for lv in levels]],
            [
                [
                    c,
                    *[
                        _rng(by[(c, lv)][metric], nd, scale) if (c, lv) in by else "–"
                        for lv in levels
                    ],
                ]
                for c in configs
            ],
        )

    lines += [table("ttft_p95_ms"), "", "## SLO goodput (req/s)", "", table("goodput_rps", 2)]
    lines += ["", "## Output throughput (tok/s)", "", table("output_tok_s")]
    lines += ["", "## TPOT p50 (ms)", "", table("tpot_p50_ms", 1)]
    lines += ["", "## Prefix-cache hit rate (%)", "", table("prefix_hit_rate", 1, 100)]
    lines += ["", "## Failure rate (%)", "", table("failure_rate", 1, 100)]
    lines += [
        "",
        "## Paired prefix-cache effect (same seed per repeat; off vs on)",
        "",
        md_table(
            [
                "max-num-seqs",
                "c",
                "pairs",
                "TTFT p95 change when off (%)",
                "goodput lost when off (req/s)",
                "same sign in every pair",
            ],
            [
                [
                    x["max_num_seqs"],
                    f"{x['level']:g}",
                    x["n_pairs"],
                    _rng(x["ttft_p95_off_vs_on_pct"], 1),
                    _rng(x["goodput_on_minus_off_rps"], 2),
                    "yes" if x["consistent_sign"] else "no",
                ]
                for x in s["prefix_effect"]
            ],
        ),
        "",
        f"Simulated vs measured reuse: the workload's shared prefix predicts a hit rate of "
        f"{wl['expected_prefix_hit_rate'] * 100:.1f}% (prefix tokens / mean input tokens; the "
        f"F1 trace replay estimated {wl['trace_reuse_ratio'] * 100:.1f}%). Measured vLLM hit rates are in the table above.",
    ]
    if s["launch_failures"]:
        lines += ["", "## Launch failures", ""]
        lines += [
            f"- {f['config']} repeat {f['repeat']}: `{f['log_tail'][-300:]!r}`"
            for f in s["launch_failures"]
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--levels", default="1,2,4,8,16")
    p.add_argument("--n", type=int, default=60)
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--gpu-util", type=float, default=0.70)
    p.add_argument("--settle-s", type=float, default=10.0)
    p.add_argument("--configs", help="comma-separated subset of config names")
    p.add_argument("--summarize-only", action="store_true")
    args = p.parse_args()
    if not args.summarize_only:
        sweep(args)
    s = summarize()
    print(render(s))


if __name__ == "__main__":
    main()
