"""Inference Lab optimizer on the lab GPU: measure a grid of serving configs, then select.

  uv run python bench/optimize.py              # measure every config not measured yet, then select
  uv run python bench/optimize.py --select-only

Grid (fixed before measuring, docs/optimizer.md): model {Qwen2.5-0.5B-Instruct fp16,
Qwen2.5-1.5B-Instruct-AWQ} x prefix caching {on, off} x max-num-seqs {8, 32}; baseline =
the compose default (0.5B, prefix caching on, max-num-seqs 32). Each config is a fresh
container (bench/rq4.py's launcher, port 8101, --gpu-memory-utilization 0.70, max-model-len
4096); the compose `vllm` service is stopped meanwhile and restarted at the end.

Per config:
- quality: the F1 app's own prompts (its retriever, context builder and system prompt, top_k
  and context budget from config/rag.yaml) for each of the 34 documented questions, answered
  with the app's generation settings (max_tokens 256, temperature 0.2) under seeds 0, 1, 2.
  Scored deterministically: `facts` = every number in the documented answer appears in the
  answer (21 questions whose answer has a number); `citations` = furnace's citation_required
  check against the doc ids actually in the context (all 34). Per question: share of seeds
  that pass.
- performance: furnace-bench on workload W1 (the F1 trace fingerprint), closed loop at
  concurrency 8, 120 requests, 3 consecutive runs (seeds 1234+r): SLO goodput (TTFT p95
  <= 500 ms), p95 TTFT, failure rate.
Selection: furnace.optimizer.select (quality non-inferiority within 5 points, paired by
question; failures <= 1%; p95 TTFT <= 500 ms; highest median goodput; overlapping goodput
ranges are reported as ties).

Output: bench/results/<date>/optimizer/{configs.json, optimizer.json, optimizer.md}; a
config that fails to launch is recorded, not skipped. Stops if AC power is lost.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from typing import Any

import httpx
import yaml
from common import (
    F1,
    W1,
    manifest,
    md_table,
    power_state,
    read_json,
    require_ac_power,
    results_dir,
    write_json,
)
from furnace.evals.checks import EvalCase, run_check
from furnace.optimizer import ConfigResult, OptimizerPolicy, select
from furnace_bench.runner import run_benchmark
from furnace_bench.schema import AdapterName, BenchPlan, BenchTarget, LengthMode
from furnace_bench.workload_spec import SLO, WorkloadSpec
from rq4 import CONTAINER, PORT, image_digest, launch, sh

MODELS = {"q05": "Qwen/Qwen2.5-0.5B-Instruct", "q15awq": "Qwen/Qwen2.5-1.5B-Instruct-AWQ"}
GRID = [
    {"name": f"{m}_pc-{'on' if pc else 'off'}_seqs-{s}", "model": MODELS[m], "prefix_cache": pc, "max_num_seqs": s}
    for m in MODELS
    for pc in (True, False)
    for s in (8, 32)
]  # fmt: skip
BASELINE = "q05_pc-on_seqs-32"
SEEDS = (0, 1, 2)
GPU_UTIL = 0.70
CONCURRENCY, N_REQUESTS, PERF_RUNS = 8, 120, 3
SLO_TTFT_MS = 500.0
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
CITE_RE = re.compile(r"\[doc:([A-Za-z0-9_.\-]+)\]")


# --------------------------------------------------------------------------- quality


def f1_prompts() -> list[dict[str, Any]]:
    """The F1 app's own rendering of each documented question: rendered inside the sandbox
    from a harness generated from F1's code (the perf gate's path), so the app's retriever,
    context budget and system prompt are used with the app's own dependencies."""
    import shutil

    from furnace.guardian.execute import prepare
    from furnace.guardian.repair.regression import render_in_sandbox

    rag = yaml.safe_load((F1 / "config" / "rag.yaml").read_text(encoding="utf-8"))
    facts = json.loads((F1 / "docs" / "facts.json").read_text(encoding="utf-8"))
    work, base, _ = prepare(F1, F1)
    try:
        rendered = render_in_sandbox(base, [f["question"] for f in facts])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    out = []
    for f, msgs in zip(facts, rendered, strict=True):
        context = next((m["content"] for m in msgs if m["role"] == "user"), "")
        out.append(
            {
                "question": f["question"],
                "reference": f["answer"],
                "messages": msgs,
                "context_ids": sorted(set(CITE_RE.findall(context))),
                "max_tokens": rag["generation"]["max_tokens"],
                "temperature": rag["generation"]["temperature"],
            }
        )
    return out


def facts_pass(reference: str, answer: str) -> bool | None:
    """Every number in the documented answer appears as a number in the answer; None when
    the documented answer has no number (not scored)."""
    nums = NUM_RE.findall(reference)
    if not nums:
        return None
    # a whole number: not inside a longer one (129, 29.50); a sentence-final "29." still counts
    return all(re.search(rf"(?<![\d.,]){re.escape(n)}(?![\d]|[.,]\d)", answer) for n in nums)


async def measure_quality(prompts: list[dict[str, Any]]) -> dict[str, Any]:
    sem = asyncio.Semaphore(CONCURRENCY)
    answers: dict[tuple[str, int], str | None] = {}

    async def one(c: httpx.AsyncClient, p: dict[str, Any], seed: int) -> None:
        async with sem:
            r = await c.post(
                "/chat/completions",
                json={
                    "model": "lab",
                    "messages": p["messages"],
                    "max_tokens": p["max_tokens"],
                    "temperature": p["temperature"],
                    "seed": seed,
                },
            )
            answers[(p["question"], seed)] = (
                r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else None
            )

    async with httpx.AsyncClient(base_url=f"http://localhost:{PORT}/v1", timeout=120) as c:
        await asyncio.gather(*(one(c, p, s) for p in prompts for s in SEEDS))
    facts: dict[str, float] = {}
    cites: dict[str, float] = {}
    failed = 0
    for p in prompts:
        f_ok, c_ok = [], []
        for s in SEEDS:
            a = answers[(p["question"], s)]
            if a is None:  # a failed request counts as a failed answer
                failed += 1
                a = ""
            fp = facts_pass(p["reference"], a)
            if fp is not None:
                f_ok.append(fp)
            case = EvalCase(input=p["question"], output=a, retrieved_ids=p["context_ids"])
            c_ok.append(run_check("citation_required", case).verdict.value == "PASS")
        if f_ok:
            facts[p["question"]] = sum(f_ok) / len(f_ok)
        cites[p["question"]] = sum(c_ok) / len(c_ok)
    return {
        "quality": {"facts": facts, "citations": cites},
        "failed_requests": failed,
        "answers": {f"{q}#{s}": a for (q, s), a in answers.items()},
    }


# ----------------------------------------------------------------------- performance


def measure_perf(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    spec = WorkloadSpec.model_validate(yaml.safe_load(W1.read_text(encoding="utf-8")))
    target = BenchTarget(
        adapter=AdapterName.vllm,
        base_url=f"http://localhost:{PORT}/v1",
        model="lab",
        metrics_url=f"http://localhost:{PORT}/metrics",
        label=cfg["name"],
        server_flags={
            "model": cfg["model"],
            "enable-prefix-caching": cfg["prefix_cache"],
            "max-num-seqs": cfg["max_num_seqs"],
            "gpu-memory-utilization": GPU_UTIL,
        },
    )
    runs = []
    for r in range(PERF_RUNS):
        plan = BenchPlan(
            concurrency_levels=[float(CONCURRENCY)],
            requests_per_level=N_REQUESTS,
            warmup_requests=8,
            length_mode=LengthMode.fixed,
            seed=1234 + r,
            slo=SLO(ttft_p95_ms=SLO_TTFT_MS),
        )
        res = asyncio.run(run_benchmark(target, spec, plan))
        lv = res.report.levels[0]
        runs.append(
            {
                "goodput_rps": lv.slo_goodput_rps,
                "ttft_p95_ms": lv.ttft_ms.p95,
                "failure_rate": lv.failure_rate,
                "prefix_hit_rate": lv.telemetry.get("prefix_cache_hit_rate"),
                "sm_clock_mhz": lv.telemetry.get("gpu_sm_clock_mhz_mean"),
            }
        )
        print(f"   perf run {r}: {runs[-1]}", flush=True)
    return runs


# --------------------------------------------------------------------------- driver


def measure(args: argparse.Namespace, out_path) -> None:
    store: dict[str, Any] = (
        read_json(out_path)
        if out_path.exists()
        else {"manifest": manifest(image_digest=image_digest()), "configs": {}}
    )
    prompts = f1_prompts()
    todo = [c for c in GRID if c["name"] not in store["configs"]]
    if args.configs:
        todo = [c for c in todo if c["name"] in args.configs.split(",")]
    sh("docker", "compose", "stop", "vllm", timeout=180)
    try:
        for cfg in todo:
            before = require_ac_power()
            print(f"== {cfg['name']}: launching", flush=True)
            t0 = time.monotonic()
            ok, log = launch(cfg, cfg["model"], GPU_UTIL)
            entry: dict[str, Any] = {"cfg": cfg}
            if not ok:
                print(f"   launch FAILED\n{log[-600:]}", flush=True)
                entry["launch_error"] = log[-1500:]
            else:
                print(f"   ready in {time.monotonic() - t0:.0f}s", flush=True)
                time.sleep(args.settle_s)
                q = asyncio.run(measure_quality(prompts))
                print(
                    f"   quality: facts {100 * sum(q['quality']['facts'].values()) / len(q['quality']['facts']):.1f}%, "
                    f"citations {100 * sum(q['quality']['citations'].values()) / len(q['quality']['citations']):.1f}%, "
                    f"failed requests {q['failed_requests']}",
                    flush=True,
                )
                entry |= {"quality": q, "perf": measure_perf(cfg)}
            after = power_state()
            entry["power"] = {"before": before, "after": after}
            if after.get("on_ac") is False:
                entry["invalid"] = "AC power lost during this config"
            store["configs"][cfg["name"]] = entry
            write_json(out_path, store)
            if entry.get("invalid"):
                raise SystemExit(
                    f"AC power lost during {cfg['name']}; recorded as invalid, stopping"
                )
    finally:
        sh("docker", "rm", "-f", CONTAINER)
        sh("docker", "compose", "--profile", "gpu", "up", "-d", "vllm", timeout=180)


def results_from(store: dict[str, Any]) -> list[ConfigResult]:
    out = []
    for name, e in store["configs"].items():
        if e.get("invalid"):
            continue
        perf = e.get("perf") or []
        out.append(
            ConfigResult(
                name=name,
                params={k: v for k, v in e["cfg"].items() if k != "name"},
                goodput_rps=[p["goodput_rps"] for p in perf],
                ttft_p95_ms=[p["ttft_p95_ms"] for p in perf],
                failure_rate=[p["failure_rate"] for p in perf],
                quality=(e.get("quality") or {}).get("quality", {}),
                launch_error=e.get("launch_error"),
            )
        )
    return out


def render(store: dict[str, Any], sel: dict[str, Any], policy: OptimizerPolicy) -> str:
    rows = []
    for r in sel["rows"]:
        if "goodput_rps" not in r:
            rows.append([r["name"], "–", "–", "–", "–", "–", "no", "; ".join(r["reasons"])])
            continue
        qv = r["quality_vs_baseline"]
        qtxt = "; ".join(
            f"{m} {r['quality_pct'][m]:.1f}%"
            + ("" if r["baseline"] else f" ({qv[m]['diff_pts']:+.1f}, {qv[m]['ci_pts'][0]:+.1f} to {qv[m]['ci_pts'][1]:+.1f})")
            for m in r["quality_pct"]
        )  # fmt: skip
        rows.append(
            [
                r["name"] + (" (baseline)" if r["baseline"] else ""),
                f"{r['goodput_rps']:.2f} ({r['goodput_range'][0]:.2f}-{r['goodput_range'][1]:.2f})",
                f"{r['ttft_p95_ms']:.0f}",
                f"{r['failure_rate']:.1%}",
                qtxt,
                "yes" if r["pareto"] else "no",
                "yes" if r["feasible"] else "no",
                "; ".join(r["reasons"]) or "–",
            ]
        )
    invalid = [n for n, e in store["configs"].items() if e.get("invalid")]
    return (
        "\n".join(
            [
                "# Inference Lab optimizer (quality-constrained config selection)",
                "",
                f"Workload W1 (F1 trace fingerprint), closed loop at concurrency {CONCURRENCY}, "
                f"{N_REQUESTS} requests x {PERF_RUNS} runs per config; quality on F1's 34 documented "
                f"questions x {len(SEEDS)} seeds with the app's own prompts. Constraints: quality not "
                f"worse than the baseline by more than {policy.quality_tol_pts:g} points (paired by "
                f"question, {policy.confidence:.0%} two-sided interval lower bound), failures <= "
                f"{policy.max_failure_rate:.0%}, p95 TTFT <= {policy.slo_ttft_p95_ms:.0f} ms. Cost: N/A "
                "(self-hosted, no $/GPU-hour set), so the objective is SLO goodput.",
                "",
                md_table(
                    [
                        "config",
                        "goodput req/s, median (range)",
                        "p95 TTFT ms",
                        "failures",
                        "quality (diff vs baseline, interval, pts)",
                        "Pareto",
                        "feasible",
                        "why not",
                    ],
                    rows,
                ),
                "",
                f"**Pick:** {sel['pick']}. **Recommendation:** {sel['recommendation']}.",
                *(
                    [f"Indistinguishable on goodput: {', '.join(sel['ties'])}."]
                    if sel["ties"]
                    else []
                ),
                *([f"Invalid (AC power lost), excluded: {', '.join(invalid)}."] if invalid else []),
                "",
                "Limits: one GPU (RTX 3050 Ti laptop, clock recorded per run), one workload, one "
                "concurrency; quality is two deterministic checks (numbers in documented answers, "
                "citation validity), not a judged answer quality; the three performance runs per "
                "config are consecutive on one container, not interleaved across configs.",
            ]
        )
        + "\n"
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--select-only", action="store_true")
    p.add_argument("--configs", help="comma-separated subset of config names to measure")
    p.add_argument("--settle-s", type=float, default=10.0)
    a = p.parse_args()
    out = results_dir("optimizer")
    path = out / "configs.json"
    if not a.select_only:
        measure(a, path)
    store = read_json(path)
    policy = OptimizerPolicy(slo_ttft_p95_ms=SLO_TTFT_MS)
    sel = select(results_from(store), BASELINE, policy)
    write_json(out / "optimizer.json", {"policy": policy.__dict__, **sel})
    text = render(store, sel, policy)
    (out / "optimizer.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
