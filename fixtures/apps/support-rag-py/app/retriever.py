"""BM25 retrieval over the markdown knowledge base, one chunk per `##` section."""

import re
from dataclasses import dataclass
from functools import lru_cache

from rank_bm25 import BM25Okapi

from app.config import ROOT

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    heading: str
    text: str


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@lru_cache
def _index() -> tuple[list[Chunk], BM25Okapi]:
    chunks: list[Chunk] = []
    for path in sorted((ROOT / "docs").glob("*.md")):
        doc_id = path.stem
        sections = re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
        for section in sections[1:]:
            heading, _, body = section.partition("\n")
            chunks.append(Chunk(doc_id, heading.strip(), body.strip()))
    return chunks, BM25Okapi([_tokens(c.heading + " " + c.text) for c in chunks])


def retrieve(query: str, top_k: int) -> list[Chunk]:
    chunks, bm25 = _index()
    scores = bm25.get_scores(_tokens(query))
    ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked[:top_k]]
