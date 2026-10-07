"""Triton RMSNorm vs the fp32 reference across shapes and dtypes. Exit 1 on any failure.

  python kernel_lab/correctness.py            (inside a CUDA + Triton environment;
                                               see kernel_lab/README.md for the container)

Tolerances are PyTorch's defaults for the output dtype (torch.testing.assert_close):
fp32 rtol 1.3e-6 / atol 1e-5, fp16 rtol 1e-3 / atol 1e-5, bf16 rtol 1.6e-2 / atol 1e-5.
The eager implementation is measured against the same reference for comparison.
"""

from __future__ import annotations

import json
import sys

import torch
from common_lab import env, out_dir
from rmsnorm import rmsnorm_eager, rmsnorm_reference, rmsnorm_triton

TOKENS = [1, 16, 512, 4096]
HIDDEN = [896, 1536, 4096]
DTYPES = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}
TOL = {"fp32": (1.3e-6, 1e-5), "fp16": (1e-3, 1e-5), "bf16": (1.6e-2, 1e-5)}


def err(out: torch.Tensor, ref: torch.Tensor) -> tuple[float, float]:
    d = (out.float() - ref).abs()
    return float(d.max()), float((d / ref.abs().clamp_min(1e-3)).max())


def main() -> int:
    torch.manual_seed(0)
    rows, failures = [], 0
    for dname, dtype in DTYPES.items():
        if dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
            rows.append({"dtype": dname, "skipped": "bf16 not supported on this GPU"})
            continue
        rtol, atol = TOL[dname]
        for t in TOKENS:
            for h in HIDDEN:
                x = torch.randn(t, h, device="cuda", dtype=dtype)
                w = (1 + 0.1 * torch.randn(h, device="cuda")).to(dtype)
                ref = rmsnorm_reference(x, w)
                y = rmsnorm_triton(x, w)
                ok = True
                try:
                    torch.testing.assert_close(
                        y.float(), ref.to(dtype).float(), rtol=rtol, atol=atol
                    )
                except AssertionError:
                    ok = False
                failures += not ok
                tri_abs, tri_rel = err(y, ref)
                eag_abs, eag_rel = err(rmsnorm_eager(x, w), ref)
                rows.append(
                    {
                        "dtype": dname,
                        "tokens": t,
                        "hidden": h,
                        "pass": ok,
                        "triton_max_abs": tri_abs,
                        "triton_max_rel": tri_rel,
                        "eager_max_abs": eag_abs,
                        "eager_max_rel": eag_rel,
                    }
                )
    res = {"env": env(), "tolerances": TOL, "rows": rows, "failures": failures}
    d = out_dir()
    (d / "correctness.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    lines = [
        f"# RMSNorm correctness ({res['env']['gpu']})",
        "",
        "Triton output vs fp32 reference, rounded to the output dtype, checked with torch.testing.assert_close "
        "at PyTorch's default tolerances for that dtype. Eager error shown for comparison.",
        "",
        "| dtype | tokens | hidden | pass | Triton max abs | Triton max rel | eager max abs | eager max rel |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        if "skipped" in r:
            lines.append(f"| {r['dtype']} | – | – | skipped: {r['skipped']} | | | | |")
        else:
            lines.append(
                f"| {r['dtype']} | {r['tokens']} | {r['hidden']} | {'yes' if r['pass'] else '**NO**'} | "
                f"{r['triton_max_abs']:.2e} | {r['triton_max_rel']:.2e} | {r['eager_max_abs']:.2e} | {r['eager_max_rel']:.2e} |"
            )
    lines += ["", f"Failures: {failures}"]
    (d / "correctness.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
