"""furnace-bench command line.

  furnace-bench run --config bench.yaml --out results/
  furnace-bench run --base-url http://localhost:8100/v1 --model lab --adapter vllm \\
      --levels 1,2,4,8,16 --n 100 --input-tokens 512 --output-tokens 128 --prefix-tokens 384
  furnace-bench mock --port 8199 --ttft-ms 50 --tpot-ms 10
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from pathlib import Path
from typing import Any

import yaml

from furnace_bench.schema import AdapterName, BenchPlan, BenchTarget, LengthMode
from furnace_bench.workload_spec import (
    SLO,
    Distribution,
    PrefixGroup,
    PrefixStats,
    WorkloadSource,
    WorkloadSpec,
)


def _levels(s: str) -> list[float]:
    return [float(x) for x in s.split(",") if x.strip()]


def _spec_from_flags(a: argparse.Namespace) -> WorkloadSpec:
    groups = (
        [PrefixGroup(prefix_hash="shared", tokens=a.prefix_tokens, share=a.prefix_share)]
        if a.prefix_tokens
        else []
    )
    return WorkloadSpec(
        name=a.workload_name,
        source=WorkloadSource.synthetic,
        synthetic=True,
        input_tokens=Distribution(p50=a.input_tokens, mean=a.input_tokens),
        output_tokens=Distribution(p50=a.output_tokens, mean=a.output_tokens),
        prefix=PrefixStats(groups=groups),
    )


def _load_config(path: str) -> tuple[BenchTarget, WorkloadSpec, BenchPlan]:
    cfg: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    target = BenchTarget.model_validate(cfg["target"])
    wl = cfg.get("workload") or {}
    if "file" in wl:
        wl_path = Path(path).parent / wl["file"]
        spec = WorkloadSpec.model_validate(yaml.safe_load(wl_path.read_text(encoding="utf-8")))
    else:
        spec = WorkloadSpec.model_validate(wl)
    plan = BenchPlan.model_validate(cfg.get("plan") or {})
    return target, spec, plan


def cmd_run(a: argparse.Namespace) -> int:
    from furnace_bench.report.writer import render_markdown, write_result
    from furnace_bench.runner import run_benchmark

    if a.config:
        target, spec, plan = _load_config(a.config)
    else:
        if not (a.base_url and a.model):
            print("either --config or --base-url and --model are required", file=sys.stderr)
            return 2
        target = BenchTarget(
            adapter=AdapterName(a.adapter),
            base_url=a.base_url,
            model=a.model,
            api_key_env=a.api_key_env,
            metrics_url=a.metrics_url,
            label=a.label,
        )
        spec = _spec_from_flags(a)
        plan = BenchPlan(
            concurrency_levels=_levels(a.levels),
            requests_per_level=a.n,
            warmup_requests=a.warmup,
            length_mode=LengthMode(a.length_mode),
            seed=a.seed,
            repeats=a.repeats,
            slo=SLO(ttft_p95_ms=a.slo_ttft_ms, tpot_p95_ms=a.slo_tpot_ms, e2e_p95_ms=a.slo_e2e_ms),
        )
    result = asyncio.run(
        run_benchmark(
            target,
            spec,
            plan,
            sample_gpu=not a.no_gpu,
            progress=lambda m: print(m, flush=True),
        )
    )
    out = write_result(result, a.out)
    print(render_markdown(result.report))
    print(f"\nwrote {out}")
    return 0


def cmd_mock(a: argparse.Namespace) -> int:
    from furnace_bench.mock_server import MockConfig, MockServer

    async def serve() -> None:
        server = MockServer(
            MockConfig(ttft_ms=a.ttft_ms, tpot_ms=a.tpot_ms, max_concurrency=a.max_concurrency),
            host=a.host,
            port=a.port,
        )
        await server.start()
        print(
            f"mock OpenAI server on {server.base_url} (ttft={a.ttft_ms}ms tpot={a.tpot_ms}ms)",
            flush=True,
        )
        await asyncio.Event().wait()

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve())
    return 0


def cmd_fingerprint(a: argparse.Namespace) -> int:
    from furnace_bench.fingerprint import fingerprint, load_traces

    records = load_traces(a.traces)
    spec = fingerprint(
        records,
        name=a.name,
        tokenizer=a.tokenizer,
        kv_capacity_tokens=a.kv_capacity_tokens,
    )
    text = yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out} ({spec.n_observed} records)")
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="furnace-bench")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fingerprint", help="derive a WorkloadSpec from JSONL call traces")
    f.add_argument("traces")
    f.add_argument("--name", default="traces")
    f.add_argument("--tokenizer", help="Hugging Face tokenizer id (falls back to an approximation)")
    f.add_argument(
        "--kv-capacity-tokens", type=int, help="simulate an LRU prefix cache of this size"
    )
    f.add_argument("--out", help="write YAML here instead of stdout")
    f.set_defaults(fn=cmd_fingerprint)

    r = sub.add_parser("run", help="run a benchmark")
    r.add_argument("--config", help="YAML with target / workload / plan")
    r.add_argument("--out", default="bench-results")
    r.add_argument("--base-url")
    r.add_argument("--model")
    r.add_argument("--adapter", default="openai_compat", choices=[x.value for x in AdapterName])
    r.add_argument("--api-key-env")
    r.add_argument("--metrics-url")
    r.add_argument("--label")
    r.add_argument("--levels", default="1,2,4,8,16")
    r.add_argument("--n", type=int, default=100, help="measured requests per level")
    r.add_argument("--warmup", type=int, default=8)
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--seed", type=int, default=1234)
    r.add_argument("--workload-name", default="cli-synthetic")
    r.add_argument("--input-tokens", type=int, default=512)
    r.add_argument("--output-tokens", type=int, default=128)
    r.add_argument("--prefix-tokens", type=int, default=0, help="shared system-prompt length")
    r.add_argument("--prefix-share", type=float, default=1.0)
    r.add_argument("--length-mode", default="fixed", choices=[x.value for x in LengthMode])
    r.add_argument("--slo-ttft-ms", type=float)
    r.add_argument("--slo-tpot-ms", type=float)
    r.add_argument("--slo-e2e-ms", type=float)
    r.add_argument("--no-gpu", action="store_true", help="do not sample local GPU via NVML")
    r.set_defaults(fn=cmd_run)

    m = sub.add_parser("mock", help="run the deterministic mock SSE server")
    m.add_argument("--host", default="127.0.0.1")
    m.add_argument("--port", type=int, default=8199)
    m.add_argument("--ttft-ms", type=float, default=50.0)
    m.add_argument("--tpot-ms", type=float, default=10.0)
    m.add_argument("--max-concurrency", type=int)
    m.set_defaults(fn=cmd_mock)

    args = p.parse_args(argv)
    # Reports contain non-ASCII characters; Windows consoles default to cp1252.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
