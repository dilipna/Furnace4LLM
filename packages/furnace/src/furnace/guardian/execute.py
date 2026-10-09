"""Execute Guard suite items against a base and a head revision.

Every item is run for real; nothing is assumed to pass. Items that cannot run
in this environment (e.g. an LLM judge without a configured key) are reported
as SKIP with the reason, never as PASS.
"""

from __future__ import annotations

import asyncio
import math
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from furnace_bench.schema import BenchTarget

from furnace.forge.harness import HARNESS_FILE, write_harness
from furnace.forge.planner import approval_test_source
from furnace.guardian.impact import ImpactResult, SuiteItem
from furnace.guardian.perf_gate import GatePolicy, compare, run_gate
from furnace.guardian.repair.regression import (
    min_shared_prefix,
    render_in_sandbox,
)
from furnace.reconstruction.build import reconstruct
from furnace.sandbox.docker_sandbox import pytest_in_sandbox

CITATION = re.compile(r"\[doc:([A-Za-z0-9_.\-]+)\]")
NOT_FOUND = re.compile(r"(?i)could not find (?:that|this|it) in")


@dataclass
class ItemResult:
    key: str
    verdict: str  # pass | fail | warn | skip | error
    detail: str
    metrics: dict[str, Any] = field(default_factory=dict)
    seconds: float = 0.0


@dataclass
class GuardContext:
    base: Path
    head: Path
    questions: list[str]
    target: BenchTarget | None
    policy: GatePolicy = field(default_factory=GatePolicy)
    judge_available: bool = False
    citation_drop_pts: float = 5.0
    max_prompt_tokens: int | None = None
    # How sandboxed code reaches the model: the lab container on the internal network.
    sandbox_base_url: str = "http://vllm:8000/v1"
    perf_repeats: int = 3
    alpha: float = 0.05  # significance level for quality regressions
    _cache: dict[str, Any] = field(default_factory=dict)


def prepare(base_root: Path, head_root: Path) -> tuple[Path, Path, Path]:
    """Disposable copies of both revisions, each with a harness generated from its own code."""
    work = Path(tempfile.mkdtemp(prefix="furnace-guard-"))
    ign = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "traces")
    base = Path(shutil.copytree(base_root, work / "base", ignore=ign))
    head = Path(shutil.copytree(head_root, work / "head", ignore=ign))
    for root in (base, head):
        if not (root / HARNESS_FILE).exists():
            write_harness(reconstruct(root))
    return work, base, head


# ---------------------------------------------------------------------------- executors


def _unit(item: SuiteItem, ctx: GuardContext) -> ItemResult:
    target = item.key.split(":", 1)[1]
    if not (ctx.head / target).exists():
        return ItemResult(item.key, "skip", f"{target} does not exist on the PR head")
    r = pytest_in_sandbox(ctx.head, target)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    return ItemResult(item.key, "pass" if r.ok else "fail", last)


def _prefix(item: SuiteItem, ctx: GuardContext) -> ItemResult:
    installed = ctx.head / "tests" / "furnace" / "test_prompt_prefix.py"
    if installed.exists():
        r = pytest_in_sandbox(ctx.head, "tests/furnace/test_prompt_prefix.py")
        return ItemResult(
            item.key, "pass" if r.ok else "fail", (r.stdout.strip().splitlines() or [""])[-1]
        )
    base_shared = min_shared_prefix(render_in_sandbox(ctx.base, ctx.questions[:4]))
    head_shared = min_shared_prefix(render_in_sandbox(ctx.head, ctx.questions[:4]))
    threshold = int(base_shared * 0.9)
    ok = head_shared >= threshold
    return ItemResult(
        item.key,
        "pass" if ok else "fail",
        f"requests share {head_shared} leading characters (base {base_shared}, need {threshold})",
        {"base_shared": base_shared, "head_shared": head_shared},
    )


def _security(item: SuiteItem, ctx: GuardContext) -> ItemResult:
    """Approval-gate tests: the installed ones if present; otherwise generated from the
    *base* revision (where the gate exists) and run against the PR head, so removing a
    gate is caught even before Forge was installed."""
    tests_dir = ctx.head / "tests" / "furnace"
    installed = sorted(tests_dir.glob("test_*_approval.py")) if tests_dir.exists() else []
    origin = "installed"
    if not installed:
        base_rec = reconstruct(ctx.base)
        gated = [
            f
            for f in base_rec.facts.of("side_effect_function")
            if f.data["approval_gate_detail"].get("present") and not f.data["observability_only"]
        ]
        if not gated:
            return ItemResult(
                item.key, "skip", "base revision has no approval-gated side effect to protect"
            )
        for f in gated:
            generated = approval_test_source(base_rec, f)
            if generated is None:
                continue
            rel, src = generated
            (ctx.head / rel).parent.mkdir(parents=True, exist_ok=True)
            (ctx.head / rel).write_text(src, encoding="utf-8")
            installed.append(ctx.head / rel)
        origin = "generated from the base revision"
        if not installed:
            return ItemResult(
                item.key, "skip", "could not generate an approval test for the gated functions"
            )
    rels = [t.relative_to(ctx.head).as_posix() for t in installed]
    r = pytest_in_sandbox(ctx.head, *rels)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    detail = f"{len(rels)} approval test(s) ({origin}): {last}"
    if not r.ok:
        reason = next(
            (
                ln.strip()
                for ln in r.stdout.splitlines()
                if "side effect executed without approval" in ln
                or "AssertionError" in ln
                or "DID NOT RAISE" in ln
            ),
            "",
        )
        detail += f" | {reason[:160]}" if reason else ""
    return ItemResult(item.key, "pass" if r.ok else "fail", detail)


async def _answers(root: Path, ctx: GuardContext) -> tuple[int, int, list[str]]:
    """Answer every question through `root`'s own prompt construction; count citation PASS."""
    target = ctx.target
    assert target is not None
    rendered = render_in_sandbox(root, ctx.questions)
    sem = asyncio.Semaphore(8)
    passes, fails = 0, []

    async def one(client: httpx.AsyncClient, msgs: list[dict[str, str]]) -> tuple[bool, str]:
        async with sem:
            r = await client.post(
                f"{target.base_url.rstrip('/')}/chat/completions",
                json={"model": target.model, "messages": msgs, "max_tokens": 256, "temperature": 0},
            )
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"] or ""
        retrieved = set(CITATION.findall(msgs[-1]["content"]))
        cited = set(CITATION.findall(answer))
        ok = (bool(cited) and cited <= retrieved) or (not cited and bool(NOT_FOUND.search(answer)))
        return ok, answer

    async with httpx.AsyncClient(timeout=120) as client:
        results = await asyncio.gather(*(one(client, m) for m in rendered))
    for ok, answer in results:
        if ok:
            passes += 1
        else:
            fails.append(answer[:160])
    return passes, len(results), fails


def _app_env(root: Path, ctx: GuardContext) -> dict[str, str] | None:
    """Environment that points the app's own client at the lab endpoint, using the env
    var names the app actually reads (found by reconstruction)."""
    rec = reconstruct(root)
    env: dict[str, str] = {}
    for c in rec.facts.of("llm_client"):
        if c.data.get("base_url_env"):
            env[c.data["base_url_env"]] = ctx.sandbox_base_url
    for call in rec.facts.of("llm_call"):
        if call.data.get("model_env") and ctx.target is not None:
            env[call.data["model_env"]] = ctx.target.model
    return env or None


def _score(rows: list[dict]) -> tuple[int, int, list[str]]:
    passes, fails = 0, []
    for row in rows:
        cited = set(CITATION.findall(row["answer"]))
        ok = (bool(cited) and cited <= set(row["retrieved"])) or (
            not cited and bool(NOT_FOUND.search(row["answer"]))
        )
        if ok:
            passes += 1
        else:
            fails.append(row["answer"][:160])
    return passes, len(rows), fails


def _app_answers(root: Path, ctx: GuardContext) -> tuple[int, int, list[str], str]:
    """Prefer the app's full answer path (harness.answer, includes output post-processing);
    fall back to prompt -> model when the handler has no sliceable answer path."""
    from furnace.guardian.repair.regression import answers_in_sandbox
    from furnace.sandbox.docker_sandbox import LAB_NETWORK

    harness_src = (root / HARNESS_FILE).read_text(encoding="utf-8")
    env = _app_env(root, ctx)
    if "def answer(" in harness_src and env:
        rows = answers_in_sandbox(root, ctx.questions, env, LAB_NETWORK)
        return (*_score(rows), "full answer path (incl. post-processing)")
    p, n, f = asyncio.run(_answers(root, ctx))
    return p, n, f, "prompt -> model only (post-processing not covered)"


def fisher_one_sided_less(k_head: int, n_head: int, k_base: int, n_base: int) -> float:
    """P(head successes <= k_head) under H0 (both revisions share one success rate),
    conditioning on the total number of successes: one-sided Fisher exact test."""
    total = k_head + k_base
    n = n_head + n_base
    denom = math.comb(n, total)
    lo = max(0, total - n_base)
    return (
        sum(math.comb(n_head, k) * math.comb(n_base, total - k) for k in range(lo, k_head + 1))
        / denom
    )


def _citation(item: SuiteItem, ctx: GuardContext) -> ItemResult:
    if ctx.target is None:
        return ItemResult(item.key, "skip", "no inference endpoint configured")
    if "base_citation" not in ctx._cache:
        ctx._cache["base_citation"] = _app_answers(ctx.base, ctx)
    bp, bn, _, _ = ctx._cache["base_citation"]
    hp, hn, hf, path = _app_answers(ctx.head, ctx)
    base_rate, head_rate = bp / bn * 100, hp / hn * 100
    drop = base_rate - head_rate
    p = fisher_one_sided_less(hp, hn, bp, bn)
    if drop > ctx.citation_drop_pts and p < ctx.alpha:
        verdict, sig = "fail", f"significant, one-sided Fisher p={p:.3f}"
    elif drop > ctx.citation_drop_pts:
        verdict, sig = "warn", f"not significant at n={hn}, one-sided Fisher p={p:.2f}"
    else:
        verdict, sig = "pass", f"p={p:.2f}"
    return ItemResult(
        item.key,
        verdict,
        f"citation contract met in {hp}/{hn} answers on the PR vs {bp}/{bn} on base ({-drop:+.1f} pts; budget -{ctx.citation_drop_pts:.0f} pts; {sig}); via {path}",
        {"base_pass": bp, "head_pass": hp, "n": hn, "p_value": p, "examples": hf[:3], "path": path},
    )


async def _prompt_tokens(root: Path, ctx: GuardContext) -> list[int]:
    assert ctx.target is not None
    rendered = render_in_sandbox(root, ctx.questions)
    base_url = ctx.target.base_url.rstrip("/").removesuffix("/v1")
    out = []
    async with httpx.AsyncClient(timeout=60) as c:
        for msgs in rendered:
            r = await c.post(
                f"{base_url}/tokenize", json={"model": ctx.target.model, "messages": msgs}
            )
            r.raise_for_status()
            out.append(int(r.json()["count"]))
    return out


def _context_budget(item: SuiteItem, ctx: GuardContext) -> ItemResult:
    if ctx.target is None or ctx.max_prompt_tokens is None:
        return ItemResult(item.key, "skip", "needs an endpoint tokenizer and a context budget")
    try:
        head = asyncio.run(_prompt_tokens(ctx.head, ctx))
        base = ctx._cache.setdefault("base_tokens", asyncio.run(_prompt_tokens(ctx.base, ctx)))
    except httpx.HTTPError as exc:
        return ItemResult(item.key, "skip", f"endpoint has no tokenizer API: {exc}")
    worst = max(head)
    verdict = "fail" if worst > ctx.max_prompt_tokens else "pass"
    return ItemResult(
        item.key,
        verdict,
        f"largest prompt {worst} tokens (base {max(base)}) against a budget of {ctx.max_prompt_tokens}; median {sorted(head)[len(head) // 2]} vs {sorted(base)[len(base) // 2]}",
        {
            "head_max": worst,
            "base_max": max(base),
            "head_median": sorted(head)[len(head) // 2],
            "base_median": sorted(base)[len(base) // 2],
        },
    )


def _endpoint_down(target: BenchTarget) -> str | None:
    """Why the endpoint cannot serve a benchmark, or None if it answers /models."""
    try:
        httpx.get(f"{target.base_url.rstrip('/')}/models", timeout=3).raise_for_status()
    except httpx.HTTPError as exc:
        return f"{type(exc).__name__} at {target.base_url}"
    return None


def _bench(item: SuiteItem, ctx: GuardContext) -> ItemResult:
    if ctx.target is None:
        return ItemResult(item.key, "skip", "no inference endpoint configured")
    down = _endpoint_down(ctx.target)
    if down:  # measured nothing: an error, never a pass
        return ItemResult(item.key, "error", f"inference endpoint unreachable ({down}); not run")
    res = run_gate(
        {"base": ctx.base, "pr_head": ctx.head},
        ctx.questions,
        ctx.target,
        repeats=ctx.perf_repeats,
        concurrency=8,
    )
    c = compare(res["base"], res["pr_head"], ctx.policy)
    if c["verdict"] == "error":
        return ItemResult(item.key, "error", f"perf gate measured nothing: {c['reason']}", c)
    verdict = {"pass": "pass", "warn": "warn", "block": "fail"}.get(c["verdict"], "error")
    hits = c.get("prefix_hit_rate") or (None, None)
    hit_txt = (
        f"; prefix-cache hit {hits[0] * 100:.0f}% -> {hits[1] * 100:.0f}%"
        if hits[0] is not None and hits[1] is not None
        else ""
    )
    sep = "runs separated" if c.get("separated") else "runs overlap"
    return ItemResult(
        item.key,
        verdict,
        f"median p95 TTFT {c['baseline']} -> {c['value']} ms ({c['change_pct']:+.1f}%, {c['verdict']}; {c['runs']} runs each, {sep}){hit_txt}",
        {
            **c,
            "reports": {k: [v.report.model_dump(mode="json") for v in vs] for k, vs in res.items()},
        },
    )


def _judge(item: SuiteItem, ctx: GuardContext) -> ItemResult:
    return ItemResult(item.key, "skip", "no judge model key configured (BYOK); judge not run")


EXECUTORS: dict[str, Callable[[SuiteItem, GuardContext], ItemResult]] = {
    "unit": _unit,
    "security": _security,
    "benchmark": _bench,
    "judge": _judge,
}
CHECKS: dict[str, Callable[[SuiteItem, GuardContext], ItemResult]] = {
    "check:prompt_prefix_stable": _prefix,
    "check:citation_required": _citation,
    "check:context_budget": _context_budget,
}


def run_items(
    items: list[SuiteItem],
    ctx: GuardContext,
    progress: Callable[[str], None] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> list[ItemResult]:
    """Run each item in order. `on_event` receives check_start/check_done dicts (live views)."""
    out = []
    for item in items:
        fn = CHECKS.get(item.key) if item.kind == "check" else EXECUTORS.get(item.kind)
        if on_event:
            on_event({"type": "check_start", "key": item.key, "kind": item.kind})
        t0 = time.monotonic()
        if fn is None:
            r = ItemResult(item.key, "skip", f"no executor for {item.kind}")
        else:
            try:
                r = fn(item, ctx)
            except Exception as exc:  # recorded per item; the run continues
                r = ItemResult(item.key, "error", f"{type(exc).__name__}: {str(exc)[:300]}")
        r.seconds = round(time.monotonic() - t0, 1)
        if progress:
            progress(f"{item.key}: {r.verdict} ({r.seconds}s) {r.detail}")
        if on_event:
            on_event(
                {
                    "type": "check_done",
                    "key": r.key,
                    "verdict": r.verdict,
                    "seconds": r.seconds,
                    "detail": r.detail[:500],
                }
            )
        out.append(r)
    return out


def verdict(results: list[ItemResult]) -> str:
    """GitHub check conclusion: any fail -> failure; any warn/error -> neutral; else success."""
    vs = {r.verdict for r in results}
    if "fail" in vs:
        return "failure"
    if vs & {"warn", "error"}:
        return "neutral"
    return "success"


def selected_items(impact: ImpactResult, suite: list[SuiteItem]) -> list[SuiteItem]:
    keys = {s.key for s in impact.impact.selected}
    return [i for i in suite if i.key in keys]
