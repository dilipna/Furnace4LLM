"""Secret detection and redaction for untrusted source text.

Runs before any excerpt is stored and before any text reaches an LLM. Findings
are reported as (kind, line) only; secret values are never persisted.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
            r"[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
        ),
    ),
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "github_token",
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b"
        ),
    ),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}\b")),
    ("groq_key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("openrouter_key", re.compile(r"\bsk-or-v1-[a-f0-9]{32,}\b")),
    ("hf_token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("db_url_password", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:([^\s@/]{6,})@")),
]

# KEY = "value" assignments whose name suggests a secret and whose value is high-entropy.
_ASSIGN = re.compile(
    r"""(?ix)
    \b([a-z0-9_]*(?:secret|token|passw(?:or)?d|api[_-]?key|access[_-]?key|private[_-]?key)[a-z0-9_]*)
    \s*[:=]\s*
    (["'])([^"'\s]{12,})\2
    """
)
_PLACEHOLDER = re.compile(
    r"(?i)^(?:x+|\*+|changeme|your[_-].*|<.*>|\$\{.*\}|example.*|dummy.*|test.*|not[-_]needed)$"
)


@dataclass(frozen=True)
class SecretFinding:
    kind: str
    start: int
    end: int
    line: int


def _entropy(s: str) -> float:
    counts = Counter(s)
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def find_secrets(text: str) -> list[SecretFinding]:
    spans: list[tuple[str, int, int]] = []
    for kind, pat in _PATTERNS:
        for m in pat.finditer(text):
            if kind == "db_url_password":
                spans.append((kind, m.start(1), m.end(1)))
            else:
                spans.append((kind, m.start(), m.end()))
    for m in _ASSIGN.finditer(text):
        value = m.group(3)
        if _PLACEHOLDER.match(value) or _entropy(value) < 3.5:
            continue
        spans.append(("assigned_secret", m.start(3), m.end(3)))
    spans.sort(key=lambda s: (s[1], -s[2]))
    merged: list[tuple[str, int, int]] = []
    for kind, s, e in spans:
        if merged and s < merged[-1][2]:
            continue  # overlapping: keep the earlier/longer span
        merged.append((kind, s, e))
    return [SecretFinding(k, s, e, text.count("\n", 0, s) + 1) for k, s, e in merged]


def redact(text: str, findings: list[SecretFinding] | None = None) -> str:
    findings = find_secrets(text) if findings is None else findings
    out: list[str] = []
    pos = 0
    for f in findings:
        out.append(text[pos : f.start])
        out.append(f"[REDACTED:{f.kind}]")
        pos = f.end
    out.append(text[pos:])
    return "".join(out)
