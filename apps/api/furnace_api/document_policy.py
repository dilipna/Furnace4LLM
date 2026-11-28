"""Local, inspectable sentence quarantine; heuristic, not a security boundary."""

from __future__ import annotations

import re

INSTRUCTION_LIKE = re.compile(
    r"<system>|\b(?:ignore\s+(?:the\s+)?(?:user|previous|above|all)|note\s+to\s+(?:ai|assistant)|"
    r"system\s+prompt|assistant\s+instruction|dear\s+ai|end\s+document\b)|^\s*(?:USER|ASSISTANT):",
    re.IGNORECASE,
)
CONTINUATION = re.compile(
    r"^\s*(?:[<\-!>\"']*\s*)?(?:say\b|respond\b|reply\b|ignore\b|"
    r"the\s+answer\s+(?:must|should)|assistant:|</system>)",
    re.IGNORECASE,
)
NUMBER_DATE = re.compile(
    r"(?<!\w)\d+(?:[.,:/-]\d+)*(?!\w)|"
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2}(?:,?\s+\d{4})?\b",
    re.IGNORECASE,
)
OUTPUT_WARNING = (
    "Check this answer carefully: it repeats a number or date found only in the "
    "AI-directed text in this document. Verify it against the original facts."
)


def quarantine(text: str) -> tuple[str, list[str]]:
    """Keep original characters in retained spans; never persist either list."""
    kept, flagged = [], []
    following = False
    for match in re.finditer(r".+?(?:[.!?](?=\s|$)|\n+|$)", text, re.DOTALL):
        sentence = match.group()
        suspicious = bool(INSTRUCTION_LIKE.search(sentence)) or (
            following and bool(CONTINUATION.search(sentence))
        )
        (flagged if suspicious else kept).append(sentence)
        following = suspicious
    return "".join(kept), flagged


def exclusive_values(output: str, retained: str, flagged: list[str]) -> list[str]:
    """Literal numeric/date provenance only, not a semantic truth or entailment check."""

    def values(text: str) -> set[str]:
        return {m.group().casefold() for m in NUMBER_DATE.finditer(text)}

    return sorted(values(output) & (values(" ".join(flagged)) - values(retained)))
