"""Deterministic checks: facts that code can decide, so no LLM judge is used.

Every check is a pure function of an `EvalCase` (and parameters) returning a
`CheckResult` with PASS/FAIL and a specific reason. Checks never call a model.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from furnace.contracts.evals import Verdict
from furnace.security.redact import find_secrets


@dataclass
class Action:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    executed: bool = True
    approved: bool | None = None


@dataclass
class EvalCase:
    """What one application request did, as far as deterministic checks need to know."""

    input: str = ""
    output: str = ""
    retrieved_ids: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    prompt_tokens: int | None = None
    ttft_ms: float | None = None
    latency_ms: float | None = None
    rendered_prompt: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    verdict: Verdict
    reason: str

    @classmethod
    def ok(cls, reason: str = "ok") -> CheckResult:
        return cls(Verdict.PASS, reason)

    @classmethod
    def fail(cls, reason: str) -> CheckResult:
        return cls(Verdict.FAIL, reason)


Check = Callable[..., CheckResult]
CHECKS: dict[str, Check] = {}


def check(name: str) -> Callable[[Check], Check]:
    def reg(fn: Check) -> Check:
        CHECKS[name] = fn
        return fn

    return reg


DEFAULT_CITATION = r"\[doc:([A-Za-z0-9_.\-]+)\]"
DEFAULT_REFUSAL = r"(?i)could not find (?:that|this|it) in"


@check("citation_required")
def citation_required(
    case: EvalCase, *, pattern: str = DEFAULT_CITATION, allow_refusal: str | None = DEFAULT_REFUSAL
) -> CheckResult:
    """At least one citation; every cited id was actually retrieved for this request.
    A documented "not found" answer may omit citations when `allow_refusal` matches."""
    cited = re.findall(pattern, case.output)
    if not cited:
        if allow_refusal and re.search(allow_refusal, case.output):
            return CheckResult.ok("documented not-found answer; no citation required")
        return CheckResult.fail("answer has no citation")
    unknown = sorted(set(cited) - set(case.retrieved_ids))
    if unknown:
        return CheckResult.fail(f"cites ids that were not retrieved: {', '.join(unknown)}")
    return CheckResult.ok(f"{len(set(cited))} cited id(s), all retrieved")


@check("json_schema_valid")
def json_schema_valid(case: EvalCase, *, schema: dict[str, Any]) -> CheckResult:
    try:
        data = json.loads(case.output)
    except json.JSONDecodeError as exc:
        return CheckResult.fail(f"output is not JSON: {exc.msg} at char {exc.pos}")
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        path = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        return CheckResult.fail(f"schema violation at {path}: {exc.message}")
    return CheckResult.ok("valid against schema")


@check("side_effect_requires_approval")
def side_effect_requires_approval(case: EvalCase, *, actions: list[str]) -> CheckResult:
    """Every executed side-effecting action in `actions` must carry an explicit approval."""
    bad = [
        a.name for a in case.actions if a.name in actions and a.executed and a.approved is not True
    ]
    if bad:
        return CheckResult.fail(f"executed without approval: {', '.join(bad)}")
    return CheckResult.ok("all side-effecting actions approved")


@check("duplicate_action")
def duplicate_action(case: EvalCase, *, actions: list[str] | None = None) -> CheckResult:
    seen: set[str] = set()
    for a in case.actions:
        if not a.executed or (actions and a.name not in actions):
            continue
        sig = a.name + json.dumps(a.args, sort_keys=True, default=str)
        if sig in seen:
            return CheckResult.fail(f"action {a.name} executed twice with identical arguments")
        seen.add(sig)
    return CheckResult.ok("no duplicate actions")


_PII = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "card_number": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
}


def _luhn(digits: str) -> bool:
    nums = [int(d) for d in digits][::-1]
    total = sum(
        n if i % 2 == 0 else (n * 2 - 9 if n * 2 > 9 else n * 2) for i, n in enumerate(nums)
    )
    return total % 10 == 0


@check("forbidden_pattern")
def forbidden_pattern(
    case: EvalCase, *, patterns: list[str] | None = None, pii: bool = True, secrets: bool = True
) -> CheckResult:
    found: list[str] = []
    if secrets:
        found += [f"secret:{f.kind}" for f in find_secrets(case.output)]
    if pii:
        if _PII["email"].search(case.output):
            found.append("pii:email")
        for m in _PII["card_number"].finditer(case.output):
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and _luhn(digits):
                found.append("pii:card_number")
                break
    for p in patterns or []:
        if re.search(p, case.output):
            found.append(f"pattern:{p}")
    if found:
        return CheckResult.fail(f"output contains {', '.join(sorted(set(found)))}")
    return CheckResult.ok("no forbidden content")


@check("latency_threshold")
def latency_threshold(
    case: EvalCase, *, max_ttft_ms: float | None = None, max_latency_ms: float | None = None
) -> CheckResult:
    if max_ttft_ms is not None:
        if case.ttft_ms is None:
            return CheckResult.fail("TTFT not recorded")
        if case.ttft_ms > max_ttft_ms:
            return CheckResult.fail(f"TTFT {case.ttft_ms:.0f} ms > {max_ttft_ms:.0f} ms")
    if max_latency_ms is not None:
        if case.latency_ms is None:
            return CheckResult.fail("latency not recorded")
        if case.latency_ms > max_latency_ms:
            return CheckResult.fail(f"latency {case.latency_ms:.0f} ms > {max_latency_ms:.0f} ms")
    return CheckResult.ok("within latency budget")


@check("context_budget")
def context_budget(case: EvalCase, *, max_prompt_tokens: int) -> CheckResult:
    if case.prompt_tokens is None:
        return CheckResult.fail("prompt token count not recorded")
    if case.prompt_tokens > max_prompt_tokens:
        return CheckResult.fail(f"prompt {case.prompt_tokens} tokens > budget {max_prompt_tokens}")
    return CheckResult.ok(f"prompt {case.prompt_tokens} tokens within {max_prompt_tokens}")


def common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


@check("prompt_prefix_stable")
def prompt_prefix_stable(
    case: EvalCase, *, other_rendered_prompt: str, min_shared_chars: int
) -> CheckResult:
    """Two different requests must share at least `min_shared_chars` of leading prompt text,
    so the serving engine's prefix cache can reuse the shared prefill."""
    if case.rendered_prompt is None:
        return CheckResult.fail("rendered prompt not available")
    shared = common_prefix_len(case.rendered_prompt, other_rendered_prompt)
    if shared < min_shared_chars:
        head = case.rendered_prompt[shared : shared + 40].replace("\n", "\\n")
        return CheckResult.fail(
            f"requests diverge after {shared} chars (need {min_shared_chars}); first difference: {head!r}"
        )
    return CheckResult.ok(f"{shared} leading chars shared")


def run_check(name: str, case: EvalCase, params: dict[str, Any] | None = None) -> CheckResult:
    if name not in CHECKS:
        return CheckResult(Verdict.ERROR, f"unknown check {name!r}")
    try:
        return CHECKS[name](case, **(params or {}))
    except TypeError as exc:
        return CheckResult(Verdict.ERROR, f"bad parameters for {name}: {exc}")
