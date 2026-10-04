"""Run deterministic evaluators over application traces.

Traces are the app's own call log (or any format furnace_bench.fingerprint can
parse). Each trace becomes an EvalCase; retrieved document ids are recovered
from the citation tags the app put in its context block.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from furnace.contracts.evals import Verdict
from furnace.evals.checks import CheckResult, EvalCase, run_check

QUESTION_RE = re.compile(r"QUESTION:\s*(.+)\s*$", re.S)


@dataclass
class EvaluatorSpec:
    key: str  # "ev:citation_required"
    check: str
    params: dict[str, Any] = field(default_factory=dict)
    failure_mode: str = ""


@dataclass
class CaseResult:
    case_index: int
    evaluator: str
    verdict: Verdict
    reason: str


@dataclass
class SuiteResult:
    results: list[CaseResult]

    def summary(self) -> dict[str, dict[str, int]]:
        out: dict[str, Counter[str]] = {}
        for r in self.results:
            out.setdefault(r.evaluator, Counter())[r.verdict.value] += 1
        return {k: dict(v) for k, v in out.items()}

    def failures(self, evaluator: str) -> list[CaseResult]:
        return [r for r in self.results if r.evaluator == evaluator and r.verdict == Verdict.FAIL]


def case_from_log(
    obj: dict[str, Any], *, citation_pattern: str = r"\[doc:([A-Za-z0-9_.\-]+)\]"
) -> EvalCase:
    """Build an EvalCase from one app call-log record (messages + completion + timings)."""
    messages = obj.get("messages") or []
    user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    context, _, _ = user.partition("QUESTION:")
    m = QUESTION_RE.search(user)
    rendered = "".join(f"{x.get('role')}\n{x.get('content', '')}\n" for x in messages)
    return EvalCase(
        input=m.group(1).strip() if m else user,
        output=obj.get("completion") or "",
        retrieved_ids=list(dict.fromkeys(re.findall(citation_pattern, context))),
        prompt_tokens=obj.get("prompt_tokens"),
        ttft_ms=obj.get("ttft_ms"),
        latency_ms=obj.get("latency_ms"),
        rendered_prompt=rendered,
        meta={"route": obj.get("route"), "model": obj.get("model"), "ts": obj.get("ts")},
    )


def load_cases(path: str | Path) -> list[EvalCase]:
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                cases.append(case_from_log(json.loads(line)))
            except json.JSONDecodeError:
                continue
    return cases


def run_suite(cases: list[EvalCase], evaluators: list[EvaluatorSpec]) -> SuiteResult:
    results: list[CaseResult] = []
    for i, case in enumerate(cases):
        for ev in evaluators:
            r: CheckResult = run_check(ev.check, case, ev.params)
            results.append(CaseResult(i, ev.key, r.verdict, r.reason))
    return SuiteResult(results)
