"""Facts: atomic, deterministic observations extracted from evidence.

A Fact is what an extractor *saw* (a call site, a route, a dependency, a config
value). Facts become Evidence rows; reconstruction turns facts into Claims and
graph nodes. Facts never contain unredacted secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from furnace.contracts.common import Locator, Observation


@dataclass
class Fact:
    kind: str  # dependency | llm_client | llm_call | route | prompt | function | call_edge | ...
    key: str  # stable natural key of the subject (usually a graph node key)
    data: dict[str, Any]
    locator: Locator
    excerpt: str
    extractor: str
    observation: Observation = Observation.direct_observation
    source: str = "repo"  # evidence source kind that produced it
    id: str = field(default="")  # assigned by FactSet ("E1", "E2", ...)


class FactSet:
    """Ordered, de-duplicated collection of facts with short stable ids."""

    def __init__(self) -> None:
        self.facts: list[Fact] = []
        self._seen: set[tuple[str, str, str]] = set()

    def add(self, fact: Fact) -> Fact | None:
        sig = (fact.kind, fact.key, fact.locator.short())
        if sig in self._seen:
            return None
        self._seen.add(sig)
        fact.id = f"E{len(self.facts) + 1}"
        self.facts.append(fact)
        return fact

    def extend(self, facts: list[Fact]) -> None:
        for f in facts:
            self.add(f)

    def of(self, kind: str) -> list[Fact]:
        return [f for f in self.facts if f.kind == kind]

    def by_id(self) -> dict[str, Fact]:
        return {f.id: f for f in self.facts}

    def __len__(self) -> int:
        return len(self.facts)
