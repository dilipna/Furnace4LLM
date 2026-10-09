"""Diagnose the gate's bimodal p95: which requests are slow, and does idle time before a run matter?

  uv run python bench/gate_noise_diag.py

Renders F1 main's prompts once (as the gate does), then runs the gate's benchmark plan
repeatedly: back-to-back, and after 5 s of idle GPU. Prints p95 and the slowest requests'
positions. Output: bench/results/<date>/gate_noise_diag.json.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from common import f1_questions, manifest, results_dir, write_json
from f1_scenarios import materialize
from furnace.guardian.execute import prepare
from furnace.guardian.repair.regression import render_in_sandbox
from furnace_bench.runner import run_benchmark
from furnace_bench.schema import AdapterName, BenchPlan, BenchTarget, LengthMode, PromptMode
from furnace_bench.workload_spec import SLO, WorkloadSource, WorkloadSpec

TARGET = BenchTarget(
    adapter=AdapterName.vllm, base_url="http://localhost:8100/v1", model="lab", label="lab vLLM"
)


async def one_run(path: str, n: int, warmup: int) -> dict:
    plan = BenchPlan(
        concurrency_levels=[8],
        requests_per_level=n,
        warmup_requests=warmup,
        cooldown_s=0,
        prompt_mode=PromptMode.replay,
        replay_path=path,
        length_mode=LengthMode.fixed,
        seed=7,
        slo=SLO(ttft_p95_ms=500.0),
    )
    spec = WorkloadSpec(name="diag", source=WorkloadSource.synthetic, synthetic=False)
    res = await run_benchmark(TARGET, spec, plan, sample_gpu=True)
    recs = sorted(res.records, key=lambda r: r.send_ts)
    ttft = [round(r.ttft_ms or 0, 1) for r in recs]
    order = sorted(range(len(ttft)), key=lambda i: -ttft[i])
    lv = res.report.levels[0]
    return {
        "p95": round(lv.ttft_ms.p95 or 0, 1),
        "p50": round(lv.ttft_ms.p50 or 0, 1),
        "slowest_positions": order[:4],
        "slowest_ms": [ttft[i] for i in order[:4]],
        "first8_ms": ttft[:8],
        "clock_mhz": lv.telemetry.get("gpu_sm_clock_mhz_mean"),
    }


def main() -> None:
    questions = f1_questions()
    tmp = Path(tempfile.mkdtemp(prefix="gate-diag-"))
    a = materialize(None, tmp / "a")
    work, base, _ = prepare(a, a)
    ref = uuid.uuid4().hex[:6]
    rendered = render_in_sandbox(base, [f"{q} (ref {ref}-{i})" for i, q in enumerate(questions)])
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)
    path = Path(tempfile.mkdtemp()) / "p.jsonl"
    path.write_text("".join(json.dumps({"messages": m, "max_tokens": 64}) + "\n" for m in rendered))
    out: dict = {"manifest": manifest(), "n_requests": len(rendered), "runs": []}
    for cond, idle, warmup in [
        ("back-to-back", 0, 0),
        ("after 5 s idle", 5, 0),
        ("after 5 s idle, 8 warmup", 5, 8),
    ]:
        for i in range(6):
            time.sleep(idle)
            r = asyncio.run(one_run(str(path), len(rendered), warmup))
            r["condition"] = cond
            out["runs"].append(r)
            print(
                cond,
                i,
                r["p95"],
                r["slowest_positions"],
                r["slowest_ms"],
                r["first8_ms"],
                flush=True,
            )
    write_json(results_dir() / "gate_noise_diag.json", out)


if __name__ == "__main__":
    main()
