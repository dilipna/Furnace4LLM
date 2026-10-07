"""RMSNorm forward: eager PyTorch vs torch.compile vs Triton, per shape and dtype.

Reports median time (triton.testing.do_bench, 20th-80th percentile range), effective
bandwidth = (read x + read weight + write y) / time, and that bandwidth as a share of a
measured device-to-device copy (`dst.copy_(src)`, read + write) on the same GPU.

  python kernel_lab/benchmark.py
"""

from __future__ import annotations

import json
import statistics

import torch
import triton
from common_lab import env, out_dir, sm_clock_mhz
from rmsnorm import rmsnorm_eager, rmsnorm_triton

TOKENS = [1, 16, 512, 4096]
HIDDEN = [896, 1536, 4096]
DTYPES = {"fp16": torch.float16, "bf16": torch.bfloat16}


def bench(fn) -> tuple[float, float, float]:
    """(median, p20, p80) in ms."""
    q = triton.testing.do_bench(fn, warmup=25, rep=200, quantiles=[0.5, 0.2, 0.8])
    return float(q[0]), float(q[1]), float(q[2])


def copy_bandwidth_gbs() -> float:
    n = 64 * 2**20  # 64M fp16 elements = 128 MiB per side
    src = torch.randn(n, device="cuda", dtype=torch.float16)
    dst = torch.empty_like(src)
    ms, _, _ = bench(lambda: dst.copy_(src))
    return 2 * n * src.element_size() / (ms * 1e-3) / 1e9


def main() -> None:
    torch.manual_seed(0)
    manifest = env()
    copy_gbs = copy_bandwidth_gbs()
    compiled = torch.compile(rmsnorm_eager, dynamic=False)
    rows, clocks = [], []
    for dname, dtype in DTYPES.items():
        if dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
            continue
        for t in TOKENS:
            for h in HIDDEN:
                x = torch.randn(t, h, device="cuda", dtype=dtype)
                w = (1 + 0.1 * torch.randn(h, device="cuda")).to(dtype)
                nbytes = (2 * t * h + h) * x.element_size()
                compiled(x, w)  # compile outside the timed region
                row = {"dtype": dname, "tokens": t, "hidden": h, "bytes": nbytes}
                for name, fn in (
                    ("eager", lambda x=x, w=w: rmsnorm_eager(x, w)),
                    ("compile", lambda x=x, w=w: compiled(x, w)),
                    ("triton", lambda x=x, w=w: rmsnorm_triton(x, w)),
                ):
                    ms, lo, hi = bench(fn)
                    row[name] = {"ms": ms, "p20": lo, "p80": hi, "gbs": nbytes / (ms * 1e-3) / 1e9}
                clocks.append(sm_clock_mhz())
                row["speedup_vs_eager"] = row["eager"]["ms"] / row["triton"]["ms"]
                row["speedup_vs_compile"] = row["compile"]["ms"] / row["triton"]["ms"]
                row["triton_pct_of_copy"] = row["triton"]["gbs"] / copy_gbs * 100
                rows.append(row)
                print(
                    f"{dname} {t}x{h}: eager {row['eager']['ms'] * 1e3:.1f}us compile {row['compile']['ms'] * 1e3:.1f}us "
                    f"triton {row['triton']['ms'] * 1e3:.1f}us ({row['triton']['gbs']:.0f} GB/s)",
                    flush=True,
                )
    seen = [c for c in clocks if c is not None]
    res = {
        "env": manifest,
        "copy_bandwidth_gbs": copy_gbs,
        "sm_clock_mhz_samples": {
            "min": min(seen),
            "max": max(seen),
            "median": statistics.median(seen),
        }
        if seen
        else None,
        "rows": rows,
    }
    d = out_dir()
    (d / "benchmark.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    clk = res["sm_clock_mhz_samples"]
    lines = [
        f"# RMSNorm forward benchmark ({manifest['gpu']}, torch {manifest['torch']}, triton {manifest['triton']})",
        "",
        f"Measured device copy bandwidth: **{copy_gbs:.0f} GB/s** (read + write). SM clock during the run: "
        + (
            f"{clk['min']:.0f}-{clk['max']:.0f} MHz (median {clk['median']:.0f})."
            if clk
            else "not available."
        ),
        "Times are medians of triton.testing.do_bench; GB/s counts x read + weight read + y write.",
        "",
        "| dtype | tokens x hidden | eager us | compile us | Triton us | Triton GB/s | % of copy | vs eager | vs compile |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['dtype']} | {r['tokens']} x {r['hidden']} | {r['eager']['ms'] * 1e3:.1f} | {r['compile']['ms'] * 1e3:.1f} | "
            f"{r['triton']['ms'] * 1e3:.1f} | {r['triton']['gbs']:.0f} | {r['triton_pct_of_copy']:.0f}% | "
            f"{r['speedup_vs_eager']:.2f}x | {r['speedup_vs_compile']:.2f}x |"
        )
    lines += [
        "",
        "Small shapes (1-16 tokens) are launch-latency bound, so GB/s there says little about the kernel; "
        "the 4096-token rows are the bandwidth comparison.",
    ]
    (d / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
