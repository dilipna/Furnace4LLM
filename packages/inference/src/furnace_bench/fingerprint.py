"""Workload fingerprinting: LLM call traces -> WorkloadSpec.

Accepted JSONL record shapes (one call per line):
  * Furnace / app call log: {"ts", "messages", "completion", "prompt_tokens",
    "completion_tokens", "latency_ms", "ttft_ms", "stream", "model", ...}
  * OpenAI-style request/response log: {"request": {"messages", "model", "stream"},
    "response": {"usage": {...}}, "ts"?, "latency_ms"?}

Prefix reuse mirrors how vLLM's automatic prefix caching works: the prompt is cut
into fixed-size token blocks, each block hash chains the previous one, and a block
is reusable if the same chained hash was seen before. We report the ratio for an
unbounded cache (upper bound) and for an LRU cache of a given capacity.

Tokenization: a Hugging Face tokenizer when available (exact for that model);
otherwise a regex approximation, recorded in the spec's `tokenizer` field.
Prompts are rendered as "role\\ncontent\\n" per message, an approximation of the
model's chat template that preserves prefix structure.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from furnace_bench.workload_spec import (
    SLO,
    ArrivalStats,
    Distribution,
    PrefixGroup,
    PrefixStats,
    TrafficClass,
    WorkloadSource,
    WorkloadSpec,
)

_APPROX = re.compile(r"\w+|[^\w\s]")


@dataclass
class TraceRecord:
    ts: float | None  # completion time, epoch seconds (if known)
    prompt: str
    system: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float | None
    ttft_ms: float | None
    stream: bool | None
    model: str | None
    tool_calls: int = 0


def _render(messages: list[dict[str, Any]]) -> tuple[str, str]:
    parts, system = [], ""
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):  # multimodal / content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        content = content or ""
        if m.get("role") == "system" and not system:
            system = content
        parts.append(f"{m.get('role', 'user')}\n{content}\n")
    return "".join(parts), system


def parse_record(obj: dict[str, Any]) -> TraceRecord | None:
    raw_req, raw_resp = obj.get("request"), obj.get("response")
    req: dict[str, Any] = raw_req if isinstance(raw_req, dict) else obj
    resp: dict[str, Any] = raw_resp if isinstance(raw_resp, dict) else {}
    messages = req.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    prompt, system = _render(messages)
    usage = resp.get("usage") or obj.get("usage") or {}
    tool_calls = 0
    for ch in resp.get("choices") or []:
        tool_calls += len((ch.get("message") or {}).get("tool_calls") or [])
    return TraceRecord(
        ts=obj.get("ts"),
        prompt=prompt,
        system=system,
        prompt_tokens=obj.get("prompt_tokens") or usage.get("prompt_tokens"),
        completion_tokens=obj.get("completion_tokens") or usage.get("completion_tokens"),
        latency_ms=obj.get("latency_ms"),
        ttft_ms=obj.get("ttft_ms"),
        stream=obj.get("stream", req.get("stream")),
        model=obj.get("model") or req.get("model"),
        tool_calls=tool_calls,
    )


def load_traces(path: str | Path) -> list[TraceRecord]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = parse_record(json.loads(line))
        except (json.JSONDecodeError, AttributeError):
            continue
        if rec is not None:
            out.append(rec)
    return out


# ---------------------------------------------------------------------------- tokenization


def make_tokenizer(name: str | None) -> tuple[Callable[[str], list[int]], str]:
    """Return (encode, label). Falls back to a deterministic regex approximation."""
    if name:
        try:
            from tokenizers import Tokenizer  # type: ignore[import-not-found]

            tok = Tokenizer.from_pretrained(name)
            return (lambda s: tok.encode(s, add_special_tokens=False).ids), name
        except Exception:  # noqa: S110 - unavailable offline / not installed: fall back
            pass

    def approx(s: str) -> list[int]:
        return [
            int.from_bytes(hashlib.blake2b(t.encode(), digest_size=4).digest(), "big")
            for t in _APPROX.findall(s)
        ]

    return approx, "regex-approx (no model tokenizer available)"


# ---------------------------------------------------------------------------- prefix reuse


def block_hashes(tokens: list[int], block: int) -> list[bytes]:
    """Chained hashes of full blocks (a partial trailing block is never cached)."""
    out: list[bytes] = []
    prev = b""
    for i in range(0, len(tokens) - len(tokens) % block, block):
        h = hashlib.blake2b(
            prev + np.asarray(tokens[i : i + block], dtype=np.int64).tobytes(), digest_size=16
        ).digest()
        out.append(h)
        prev = h
    return out


def prefix_reuse(
    token_lists: Iterable[list[int]], block: int = 16, lru_capacity_blocks: int | None = None
) -> tuple[float, float | None]:
    """Fraction of prompt tokens served from cache, replaying prompts in order.

    Returns (unbounded_ratio, lru_ratio_or_None). With an LRU, a hit refreshes the
    block; misses insert it and evict the least recently used block when full.
    """
    seen: set[bytes] = set()
    lru: OrderedDict[bytes, None] = OrderedDict()
    total = hit_inf = hit_lru = 0
    for toks in token_lists:
        total += len(toks)
        hashes = block_hashes(toks, block)
        # vLLM reuses the longest cached *prefix*: stop at the first miss.
        for h in hashes:
            if h in seen:
                hit_inf += block
            else:
                break
        seen.update(hashes)
        if lru_capacity_blocks:
            for h in hashes:
                if h in lru:
                    hit_lru += block
                    lru.move_to_end(h)
                else:
                    break
            for h in hashes:
                lru[h] = None
                lru.move_to_end(h)
                while len(lru) > lru_capacity_blocks:
                    lru.popitem(last=False)
    if total == 0:
        return 0.0, None
    return hit_inf / total, (hit_lru / total if lru_capacity_blocks else None)


def _common_prefix_len(a: list[int], b: list[int]) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


# ---------------------------------------------------------------------------- distributions


def distribution(values: Sequence[float | int | None], bins: int = 12) -> Distribution:
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return Distribution()
    edges = np.unique(np.quantile(arr, np.linspace(0, 1, bins + 1)))
    hist: list[tuple[float, int]] = []
    if edges.size >= 2:
        counts, e = np.histogram(arr, bins=edges)
        hist = [(float(e[i + 1]), int(c)) for i, c in enumerate(counts)]
    else:
        hist = [(float(arr[0]), int(arr.size))]
    return Distribution(
        n=int(arr.size),
        mean=float(arr.mean()),
        p50=float(np.percentile(arr, 50)),
        p95=float(np.percentile(arr, 95)),
        p99=float(np.percentile(arr, 99)),
        min=float(arr.min()),
        max=float(arr.max()),
        hist=hist,
    )


def _arrival(records: list[TraceRecord]) -> tuple[ArrivalStats, float | None]:
    timed = [r for r in records if r.ts is not None]
    if len(timed) < 2:
        return ArrivalStats(), None
    # Logged ts is completion time; start = ts - latency when latency is known.
    starts = sorted(float(r.ts) - (r.latency_ms or 0.0) / 1000.0 for r in timed)  # type: ignore[arg-type]
    window = starts[-1] - starts[0]
    gaps = np.diff(starts)
    cv = float(gaps.std() / gaps.mean()) if gaps.size > 1 and gaps.mean() > 0 else None
    events: list[tuple[float, int]] = []
    for r in timed:
        end = float(r.ts)  # type: ignore[arg-type]
        start = end - (r.latency_ms or 0.0) / 1000.0
        events += [(start, 1), (end, -1)]
    events.sort(key=lambda e: (e[0], e[1]))
    cur = peak = 0
    time_at: dict[int, float] = {}
    last_t = events[0][0]
    for t, d in events:
        time_at[cur] = time_at.get(cur, 0.0) + (t - last_t)
        last_t = t
        cur += d
        peak = max(peak, cur)
    total_t = sum(time_at.values()) or 1.0
    hist = [(k, v / total_t) for k, v in sorted(time_at.items())]
    return (
        ArrivalStats(
            mean_rps=(len(timed) - 1) / window if window > 0 else None,
            cv_interarrival=cv,
            peak_concurrency=peak,
            concurrency_hist=hist,
        ),
        window,
    )


def fingerprint(
    records: list[TraceRecord],
    *,
    name: str = "traces",
    tokenizer: str | None = None,
    block_size: int = 16,
    kv_capacity_tokens: int | None = None,
    slo: SLO | None = None,
) -> WorkloadSpec:
    if not records:
        raise ValueError("no usable trace records")
    encode, tok_label = make_tokenizer(tokenizer)
    token_lists = [encode(r.prompt) for r in records]
    sys_lens = [len(encode(r.system)) for r in records if r.system]
    in_tokens = [
        r.prompt_tokens if r.prompt_tokens is not None else len(t)
        for r, t in zip(records, token_lists, strict=True)
    ]
    out_tokens = [r.completion_tokens for r in records if r.completion_tokens is not None]
    cap_blocks = kv_capacity_tokens // block_size if kv_capacity_tokens else None
    reuse_inf, reuse_lru = prefix_reuse(token_lists, block_size, cap_blocks)

    # Groups: requests sharing an identical system message; tokens = their common prefix.
    by_system: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        by_system.setdefault(
            hashlib.sha256(r.system.encode()).hexdigest()[:12] if r.system else "", []
        ).append(i)
    groups = []
    for h, idxs in sorted(by_system.items(), key=lambda kv: -len(kv[1])):
        if not h or len(idxs) < 2:
            continue
        common = min(_common_prefix_len(token_lists[idxs[0]], token_lists[j]) for j in idxs[1:])
        groups.append(PrefixGroup(prefix_hash=h, tokens=common, share=len(idxs) / len(records)))

    arrival, window = _arrival(records)
    streams = [r.stream for r in records if r.stream is not None]
    stream_ratio = sum(streams) / len(streams) if streams else None
    in_dist, out_dist = distribution(in_tokens), distribution(out_tokens)

    classes: list[TrafficClass] = []
    if stream_ratio is not None and stream_ratio >= 0.5 and out_dist.p95 and out_dist.p95 <= 1024:
        classes.append(TrafficClass.interactive)
    if stream_ratio is not None and stream_ratio < 0.5:
        classes.append(TrafficClass.batch)
    if in_dist.p95 > 8000:
        classes.append(TrafficClass.long_context)
    if arrival.peak_concurrency and arrival.peak_concurrency > 32:
        classes.append(TrafficClass.high_concurrency)
    if any(r.tool_calls for r in records):
        classes.append(TrafficClass.tool_agent)

    models = Counter(r.model for r in records if r.model)
    n = len(records)
    return WorkloadSpec(
        name=name,
        source=WorkloadSource.traces,
        synthetic=False,
        model=models.most_common(1)[0][0] if models else None,
        tokenizer=tok_label,
        n_observed=n,
        window_seconds=window,
        input_tokens=in_dist,
        output_tokens=out_dist,
        system_prompt_tokens=distribution(sys_lens) if sys_lens else None,
        prefix=PrefixStats(
            block_size=block_size,
            reuse_ratio_infinite=reuse_inf,
            reuse_ratio_lru=reuse_lru,
            lru_capacity_tokens=kv_capacity_tokens,
            groups=groups,
        ),
        arrival=arrival,
        streaming_ratio=stream_ratio,
        traffic_class=classes,
        slo=slo or SLO(),
        field_provenance={
            "input_tokens": f"traces: {n} records (server usage where logged, else {tok_label})",
            "output_tokens": f"traces: {len(out_tokens)} records with completion token counts",
            "prefix": f"block-hash replay of {n} rendered prompts, block={block_size}, tokenizer={tok_label}",
            "arrival": f"traces: {len([r for r in records if r.ts is not None])} timestamped records",
        },
    )
