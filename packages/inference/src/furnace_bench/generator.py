"""Turn a WorkloadSpec into concrete chat-completion payloads.

Synthetic mode builds prompts from a fixed vocabulary so that lengths are
controllable and runs are reproducible from the seed. Shared-prefix groups are
placed in the system message (where real apps put long, stable instructions) so
the server's prefix cache sees the same reuse structure the workload measured.

Prompt *token* counts are targets; the actual counts reported in results come
from the server's usage field (or a tokenizer), never from these targets.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from furnace_bench.schema import BenchPlan, LengthMode, PromptMode
from furnace_bench.workload_spec import Distribution, PrefixGroup, WorkloadSpec

# Common short English words; for BPE tokenizers used by Llama/Qwen/GPT families
# " word" is almost always a single token, so words ~= tokens (calibrated at runtime
# when the server can tokenize; see adapters.Adapter.tokenize).
VOCAB = [
    "time",
    "person",
    "year",
    "way",
    "day",
    "thing",
    "man",
    "world",
    "life",
    "hand",
    "part",
    "child",
    "eye",
    "woman",
    "place",
    "work",
    "week",
    "case",
    "point",
    "government",
    "company",
    "number",
    "group",
    "problem",
    "fact",
    "be",
    "have",
    "do",
    "say",
    "get",
    "make",
    "go",
    "know",
    "take",
    "see",
    "come",
    "think",
    "look",
    "want",
    "give",
    "use",
    "find",
    "tell",
    "ask",
    "seem",
    "feel",
    "try",
    "leave",
    "call",
    "good",
    "new",
    "first",
    "last",
    "long",
    "great",
    "little",
    "own",
    "other",
    "old",
    "right",
    "big",
    "high",
    "different",
    "small",
    "large",
    "next",
    "early",
    "young",
    "important",
    "few",
    "public",
    "bad",
    "same",
    "able",
    "system",
    "order",
    "account",
    "billing",
    "invoice",
    "refund",
    "policy",
    "support",
    "ticket",
    "answer",
    "question",
    "document",
    "section",
    "page",
    "model",
    "server",
    "request",
    "reply",
    "status",
    "error",
    "update",
    "change",
    "review",
    "customer",
    "product",
    "service",
    "plan",
    "team",
    "report",
    "data",
    "table",
]


@dataclass
class GeneratedRequest:
    messages: list[dict[str, str]]
    max_tokens: int
    target_input_tokens: int
    prefix_group: str | None
    extra: dict[str, Any]


def sample_lengths(
    dist: Distribution, n: int, rng: np.random.Generator, *, floor: int = 1
) -> np.ndarray:
    """Sample n integer lengths from an empirical distribution summary.

    Priority: histogram -> log-normal fit through p50/p95 -> constant mean.
    """
    if dist.hist:
        edges = [0.0] + [float(e) for e, _ in dist.hist]
        counts = np.asarray([c for _, c in dist.hist], dtype=float)
        if counts.sum() > 0:
            bins = rng.choice(len(counts), size=n, p=counts / counts.sum())
            lo = np.asarray(edges[:-1])[bins]
            hi = np.asarray(edges[1:])[bins]
            vals = rng.uniform(lo, hi)
            return np.maximum(floor, np.round(vals)).astype(int)
    if dist.p50 > 0 and dist.p95 > dist.p50:
        mu = math.log(dist.p50)
        sigma = (math.log(dist.p95) - mu) / 1.6448536269514722
        vals = rng.lognormal(mu, sigma, size=n)
        cap = dist.max if dist.max > 0 else dist.p99 * 2 if dist.p99 > 0 else vals.max()
        return np.clip(np.round(vals), floor, cap).astype(int)
    const = dist.p50 or dist.mean or floor
    return np.full(n, max(floor, round(const)), dtype=int)


def _words(rng: np.random.Generator, n: int) -> str:
    if n <= 0:
        return ""
    idx = rng.integers(0, len(VOCAB), size=n)
    return " ".join(VOCAB[i] for i in idx)


def _prefix_groups(spec: WorkloadSpec, typical_input: int) -> list[PrefixGroup]:
    if spec.prefix.groups:
        return spec.prefix.groups
    ratio = spec.prefix.reuse_ratio_infinite
    if ratio and ratio > 0:
        # One shared prefix whose length reproduces the measured reuse ratio.
        return [PrefixGroup(prefix_hash="g0", tokens=int(ratio * typical_input), share=1.0)]
    return []


class SyntheticGenerator:
    def __init__(
        self, spec: WorkloadSpec, plan: BenchPlan, *, words_per_token: float = 1.0
    ) -> None:
        self.spec = spec
        self.plan = plan
        self.words_per_token = words_per_token
        self.rng = np.random.default_rng(plan.seed)
        typical_in = int(spec.input_tokens.p50 or spec.input_tokens.mean or 256)
        self.groups = _prefix_groups(spec, typical_in)
        prefix_rng = np.random.default_rng(plan.seed + 7919)
        self.prefix_text = {
            g.prefix_hash: _words(prefix_rng, int(g.tokens * words_per_token)) for g in self.groups
        }

    def generate(self, n: int) -> list[GeneratedRequest]:
        ins = sample_lengths(self.spec.input_tokens, n, self.rng, floor=4)
        if self.spec.output_tokens.n or self.spec.output_tokens.p50 or self.spec.output_tokens.mean:
            outs = sample_lengths(self.spec.output_tokens, n, self.rng, floor=1)
        else:
            outs = np.full(n, 128, dtype=int)
        shares = np.asarray([g.share for g in self.groups], dtype=float)
        p_none = max(0.0, 1.0 - shares.sum())
        reqs: list[GeneratedRequest] = []
        for i in range(n):
            group: PrefixGroup | None = None
            if self.groups:
                choice = self.rng.choice(
                    len(self.groups) + 1, p=np.append(shares, p_none) / (shares.sum() + p_none)
                )
                group = self.groups[choice] if choice < len(self.groups) else None
            target_in = int(ins[i])
            prefix_tokens = min(group.tokens, target_in - 2) if group else 0
            suffix_tokens = max(2, target_in - prefix_tokens)
            # Unique request id up front in the *user* message keeps suffixes distinct
            # without disturbing the shared system-prompt prefix.
            user = f"[{i}] " + _words(self.rng, int(suffix_tokens * self.words_per_token))
            messages: list[dict[str, str]] = []
            if group:
                messages.append({"role": "system", "content": self.prefix_text[group.prefix_hash]})
            messages.append({"role": "user", "content": user})
            max_tokens = int(outs[i])
            if self.plan.length_mode == LengthMode.natural:
                max_tokens = int(max(max_tokens, self.spec.output_tokens.p99 or 0, 64) * 2)
            reqs.append(
                GeneratedRequest(
                    messages=messages,
                    max_tokens=max_tokens,
                    target_input_tokens=target_in,
                    prefix_group=group.prefix_hash if group else None,
                    extra={},
                )
            )
        return reqs


def load_replay(path: str | Path, n: int, seed: int) -> list[GeneratedRequest]:
    """Load payloads from JSONL. Each line: {"messages": [...], "max_tokens"?: int, ...}
    (other keys are passed through). Cycles through the file to produce n requests,
    in a seeded shuffled order."""
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError(f"replay file {path} is empty")
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(rows))
    out: list[GeneratedRequest] = []
    for i in range(n):
        row = dict(rows[order[i % len(rows)]])
        messages = row.pop("messages")
        max_tokens = int(row.pop("max_tokens", 256))
        group = row.pop("prefix_group", None)
        row.pop("model", None)
        row.pop("stream", None)
        out.append(GeneratedRequest(messages, max_tokens, 0, group, row))
    return out


def build_requests(
    spec: WorkloadSpec, plan: BenchPlan, n: int, *, words_per_token: float = 1.0
) -> list[GeneratedRequest]:
    if plan.prompt_mode == PromptMode.replay:
        if not plan.replay_path:
            raise ValueError("prompt_mode=replay requires plan.replay_path")
        return load_replay(plan.replay_path, n, plan.seed)
    return SyntheticGenerator(spec, plan, words_per_token=words_per_token).generate(n)
