"""Confidence and provenance reconciliation.

For one (subject, predicate), candidate values from different evidence sources
are grouped by normalized value. Each group's support is a noisy-OR of its
sources' priors (independent evidence accumulates); its confidence is then
discounted by the support of competing values. Two or more surviving values
form a conflict group: every value is kept and shown, none is chosen silently.

The priors are hand-set; FurnaceBench RQ1 measures their calibration instead of
asserting it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from furnace.contracts.common import ClaimStatus, Method, Observation

PRIORS: dict[str, float] = {
    "ast": 0.95,  # observed in source code
    "ast_heuristic": 0.7,  # source pattern that needs interpretation (e.g. approval gate)
    "config": 0.9,  # compose / config files
    "trace": 0.9,  # production traces
    "dependency": 0.6,  # declared but possibly unused
    "readme": 0.5,  # documentation claims
    "vlm": 0.45,  # read from a screenshot / diagram
    "llm": 0.4,  # semantic inference by a language model
    "absence": 0.6,  # "searched and found nothing"
}
CONTRADICTION_WEIGHT = 0.5

_METHOD_OF = {
    "ast": Method.deterministic,
    "ast_heuristic": Method.deterministic,
    "config": Method.deterministic,
    "dependency": Method.deterministic,
    "absence": Method.deterministic,
    "readme": Method.deterministic,
    "trace": Method.trace,
    "vlm": Method.vlm,
    "llm": Method.llm,
}


@dataclass
class Candidate:
    value: Any
    source: str  # key of PRIORS
    fact_ids: list[str]
    rationale: str = ""
    # direct: the value itself was observed (not inferred) in this source
    direct: bool = True


@dataclass
class ClaimRec:
    subject_key: str
    predicate: str
    value: Any
    confidence: float
    method: Method
    observation: Observation
    status: ClaimStatus
    supports: list[str]
    contradicts: list[str]
    conflict_group: str | None
    rationale: str
    sources: list[str] = field(default_factory=list)


def noisy_or(ps: list[float]) -> float:
    out = 1.0
    for p in ps:
        out *= 1.0 - p
    return 1.0 - out


def _default_norm(v: Any) -> Any:
    return v.strip().lower() if isinstance(v, str) else v


def reconcile(
    subject_key: str,
    predicate: str,
    candidates: list[Candidate],
    *,
    normalize: Callable[[Any], Any] = _default_norm,
) -> list[ClaimRec]:
    """Return one ClaimRec per distinct value, highest confidence first."""
    if not candidates:
        return []
    groups: dict[Any, list[Candidate]] = {}
    for c in candidates:
        groups.setdefault(normalize(c.value), []).append(c)
    support = {k: noisy_or([PRIORS[c.source] for c in cs]) for k, cs in groups.items()}
    conflict = (
        hashlib.sha256(f"{subject_key}|{predicate}".encode()).hexdigest()[:12]
        if len(groups) > 1
        else None
    )
    out: list[ClaimRec] = []
    for k, cs in groups.items():
        others = [support[o] for o in groups if o != k]
        oppose = noisy_or(others)
        conf = support[k] * (1.0 - CONTRADICTION_WEIGHT * oppose)
        sources = sorted({c.source for c in cs})
        methods = {_METHOD_OF[s] for s in sources}
        method = methods.pop() if len(methods) == 1 else Method.reconciled
        code_direct = any(c.direct and c.source in ("ast", "config", "trace") for c in cs)
        out.append(
            ClaimRec(
                subject_key=subject_key,
                predicate=predicate,
                # display the value as written by the strongest source
                value=max(cs, key=lambda c: PRIORS[c.source]).value,
                confidence=round(conf, 3),
                method=method,
                observation=Observation.direct_observation
                if code_direct
                else Observation.inference,
                status=ClaimStatus.contested if conflict else ClaimStatus.supported,
                supports=sorted({f for c in cs for f in c.fact_ids}),
                contradicts=sorted(
                    {f for o, ocs in groups.items() if o != k for c in ocs for f in c.fact_ids}
                ),
                conflict_group=conflict,
                rationale="; ".join(c.rationale for c in cs if c.rationale),
                sources=sources,
            )
        )
    out.sort(key=lambda r: -r.confidence)
    return out
