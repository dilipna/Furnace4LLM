"""Small deterministic BM25 over in-memory sections; no embeddings or persistence."""

from __future__ import annotations

import math
import re
from collections import Counter

STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "what",
        "which",
        "who",
        "when",
        "where",
        "how",
        "do",
        "does",
        "did",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "and",
        "or",
        "it",
        "this",
        "that",
        "please",
        "only",
        "reply",
        "with",
        "from",
        "document",
        "according",
    ]
)


def terms(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.casefold()) if t not in STOP]


def retrieve(parts: list[str], question: str, limit: int = 3) -> list[dict]:
    tokens = [Counter(terms(part)) for part in parts]
    lengths = [sum(t.values()) for t in tokens]
    average = max(1, sum(lengths) / max(1, len(parts)))
    query = sorted(set(terms(question)))
    frequencies = {term: sum(term in t for t in tokens) for term in query}
    ranked = []
    offset = 0
    for i, (part, counts, length) in enumerate(zip(parts, tokens, lengths, strict=True)):
        score = 0.0
        for term in query:
            tf = counts[term]
            if tf:
                idf = math.log(
                    1 + (len(parts) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
                )
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average))
        if score > 0:
            ranked.append(
                {
                    "section": i + 1,
                    "start": offset,
                    "end": offset + len(part),
                    "text": part,
                    "rank_score": round(score, 6),
                }
            )
        offset += len(part)
    return sorted(
        sorted(ranked, key=lambda r: (-r["rank_score"], r["section"]))[:limit],
        key=lambda r: r["section"],
    )
