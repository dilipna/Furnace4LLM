"""RMSNorm: an fp32 reference, the eager PyTorch form, and a Triton kernel.

    y = x / sqrt(mean(x^2) + eps) * weight      (per row, over the hidden dimension)

This is the normalization used by Qwen2/Llama-family models before attention and MLP
blocks. It is memory-bound: each element is read once and written once, so the right
yardstick is effective bandwidth against a measured device copy, not FLOPs.
"""

from __future__ import annotations

import torch

try:  # Triton exists on Linux CUDA builds of PyTorch; the reference works anywhere.
    import triton
    import triton.language as tl
except ImportError:  # pragma: no cover - CPU-only environments
    triton = None
    tl = None

EPS = 1e-6


def rmsnorm_reference(x: torch.Tensor, weight: torch.Tensor, eps: float = EPS) -> torch.Tensor:
    """fp32 reference: the ground truth for correctness, regardless of input dtype."""
    xf = x.float()
    rms = torch.rsqrt(xf.pow(2).mean(dim=-1, keepdim=True) + eps)
    return xf * rms * weight.float()


def rmsnorm_eager(x: torch.Tensor, weight: torch.Tensor, eps: float = EPS) -> torch.Tensor:
    """The common eager implementation (as in Hugging Face Qwen2RMSNorm): fp32 accumulate,
    cast back to the input dtype, then scale."""
    xf = x.float()
    xf = xf * torch.rsqrt(xf.pow(2).mean(-1, keepdim=True) + eps)
    return weight * xf.to(x.dtype)


if triton is not None:

    @triton.jit
    def _rmsnorm_fwd(X, W, Y, stride_x, stride_y, N, eps, BLOCK: tl.constexpr):  # type: ignore[misc]
        # One program per row; the whole row fits in one block (hidden <= BLOCK).
        row = tl.program_id(0)
        cols = tl.arange(0, BLOCK)
        mask = cols < N
        x = tl.load(X + row * stride_x + cols, mask=mask, other=0.0).to(tl.float32)
        mean_sq = tl.sum(x * x, axis=0) / N
        rstd = 1.0 / tl.sqrt(mean_sq + eps)
        w = tl.load(W + cols, mask=mask, other=0.0).to(tl.float32)
        y = x * rstd * w
        tl.store(Y + row * stride_y + cols, y.to(Y.dtype.element_ty), mask=mask)


def rmsnorm_triton(x: torch.Tensor, weight: torch.Tensor, eps: float = EPS) -> torch.Tensor:
    if triton is None:
        raise RuntimeError("Triton is not available in this environment")
    if x.shape[-1] != weight.shape[0]:
        raise ValueError("hidden size mismatch")
    x2 = x.reshape(-1, x.shape[-1])
    if x2.stride(-1) != 1:
        x2 = x2.contiguous()
    y = torch.empty_like(x2)
    n = x2.shape[1]
    block = triton.next_power_of_2(n)
    if block > 65536 // x.element_size():
        raise ValueError(f"hidden size {n} too large for a single-block row")
    num_warps = min(max(block // 256, 1), 16)
    _rmsnorm_fwd[(x2.shape[0],)](
        x2, weight, y, x2.stride(0), y.stride(0), n, eps, BLOCK=block, num_warps=num_warps
    )
    return y.reshape(x.shape)
