"""Evidence-triggered Blueprint rules.

A rule fires only when the reconstructed graph shows the condition it is about,
and its `why` is built from this application's own facts (paths, token counts,
config values). There is no generic checklist: no evidence, no recommendation.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from furnace.code_intel.facts import Fact
from furnace.contracts.appspec import SideEffect
from furnace.contracts.blueprint import Area, Recommendation
from furnace.contracts.common import Priority
from furnace.reconstruction.build import Reconstruction

CITATION_INSTRUCTION = re.compile(r"(?i)\bcit(e|ation)s?\b|\[doc:|\[source")
ESCALATION_MARKER = re.compile(r"(?m)^\s*([A-Z_]{4,}):\s*<")
CHARS_PER_TOKEN = 4.0  # approximation used only where no tokenizer is available; stated in text


@dataclass
class Ctx:
    rec: Reconstruction
    fact_uuid: dict[str, Any]

    @property
    def spec(self):
        return self.rec.appspec

    def facts(self, kind: str) -> list[Fact]:
        return self.rec.facts.of(kind)

    def ev(self, *facts: Fact) -> list[Any]:
        return [self.fact_uuid[f.id] for f in facts if f.id in self.fact_uuid]

    def text_at(self, f: Fact) -> str:
        loc = f.locator
        if not loc.path:
            return ""
        file = next((x for x in self.rec.inventory.files if x.path == loc.path), None)
        if file is None:
            return ""
        lines = self.rec.inventory.read(file).splitlines()
        start = (loc.line_start or 1) - 1
        end = loc.line_end or start + 1
        return "\n".join(lines[start:end])


Rule = Callable[[Ctx], list[Recommendation]]
RULES: list[Rule] = []


def rule(fn: Rule) -> Rule:
    RULES.append(fn)
    return fn


def _tokens(chars: int) -> int:
    return round(chars / CHARS_PER_TOKEN)


def _an(word: str) -> str:
    return f"an {word}" if word[:1].lower() in "aeiou" else f"a {word}"


SDK_DEFAULT_TIMEOUT = {
    "openai": "10 minutes",
    "azure_openai": "10 minutes",
    "anthropic": "10 minutes",
}


# ---------------------------------------------------------------------------- security


@rule
def tool_without_approval(ctx: Ctx) -> list[Recommendation]:
    out = []
    for tool in ctx.spec.tools:
        if (
            tool.side_effect.value in (SideEffect.write, SideEffect.external)
            and tool.approval_gate.value is False
        ):
            f = next(x for x in ctx.facts("side_effect_function") if x.key == tool.key)
            effects = ", ".join(e["call"] for e in f.data["effects"])
            out.append(
                Recommendation(
                    rule_id="sec.tool_approval_boundary",
                    area=Area.security,
                    title=f"Put a deterministic approval boundary in front of `{tool.name}`",
                    why=(
                        f"`{tool.name}` ({tool.locator.short()}) performs {_an(tool.side_effect.value.value)} side effect "
                        f"({effects}) and no approval parameter guards it before the call. If an LLM decision "
                        "reaches this function, a wrong or injected answer becomes a real action."
                    ),
                    evidence_ids=ctx.ev(f),
                    priority=Priority.P0,
                    confidence=min(tool.side_effect.confidence, tool.approval_gate.confidence),
                    verification_method=(
                        f"Deterministic check: every trace that executes `{tool.name}` must carry an explicit "
                        "user approval; a unit test calls it with approved=False and expects refusal."
                    ),
                    node_keys=[tool.key],
                    forge_action="add_approval_boundary",
                )
            )
    return out


@rule
def tool_approval_regression_guard(ctx: Ctx) -> list[Recommendation]:
    out = []
    for tool in ctx.spec.tools:
        if tool.approval_gate.value is True:
            f = next(x for x in ctx.facts("side_effect_function") if x.key == tool.key)
            gate = f.data["approval_gate_detail"]
            out.append(
                Recommendation(
                    rule_id="sec.approval_gate_regression_test",
                    area=Area.security,
                    title=f"Lock in the approval gate on `{tool.name}` with a regression test",
                    why=(
                        f"`{tool.name}` ({tool.locator.short()}) is guarded by `if not {gate['param']}` on line "
                        f"{gate['guard_line']}, but nothing fails if a refactor removes it. This is the only thing "
                        f"standing between a model answer and {_an(tool.side_effect.value.value)} side effect."
                    ),
                    evidence_ids=ctx.ev(f),
                    priority=Priority.P1,
                    confidence=tool.approval_gate.confidence,
                    verification_method=f"Security test: call `{tool.name}` with {gate['param']}=False and assert no outbound request is made.",
                    node_keys=[tool.key],
                    forge_action="security_test_approval_gate",
                )
            )
    return out


# ---------------------------------------------------------------------------- reliability


@rule
def llm_call_without_timeout(ctx: Ctx) -> list[Recommendation]:
    """One finding listing every LLM call site that has no timeout."""
    missing = [c for c in ctx.spec.llm_calls if not c.has_timeout]
    if not missing:
        return []
    facts = [next(x for x in ctx.facts("llm_call") if x.key == c.key) for c in missing]
    sdks = set()
    for c in missing:
        client = next((x for x in ctx.facts("llm_client") if x.key == c.endpoint_key), None)
        sdks.add(client.data.get("sdk") if client else None)
    defaults = {SDK_DEFAULT_TIMEOUT.get(s or "") for s in sdks}
    if len(sdks) == 1 and None not in defaults:
        sdk = next(iter(sdks))
        wait = f"the {sdk} SDK default ({SDK_DEFAULT_TIMEOUT[sdk or '']}) applies"
    else:
        wait = "only library defaults (up to 10 minutes for the OpenAI and Anthropic SDKs) apply"
    streaming = any(c.streaming is not None and c.streaming.value is True for c in missing)
    if len(missing) == 1:
        where = f"`{missing[0].api}` at {missing[0].locator.short()} sets"
    else:
        where = f"{len(missing)} LLM call sites ({', '.join(c.locator.short() for c in missing[:5])}{'…' if len(missing) > 5 else ''}) set"
    return [
        Recommendation(
            rule_id="rel.llm_timeout",
            area=Area.reliability,
            title="Set explicit timeouts on the LLM call"
            if len(missing) == 1
            else f"Set explicit timeouts on {len(missing)} LLM calls",
            why=(
                f"{where} no timeout on the call or its client, so {wait}. "
                + (
                    "A stalled stream holds the HTTP response open for the user for that whole time."
                    if streaming
                    else "A stalled request blocks the caller for that whole time."
                )
            ),
            evidence_ids=ctx.ev(*facts),
            priority=Priority.P0,
            confidence=0.9,
            verification_method="Fault-injection test against a mock endpoint that stalls after the first token; the request must fail within the configured budget.",
            node_keys=[c.key for c in missing],
            forge_action="add_llm_timeout",
        )
    ]


@rule
def no_fallback(ctx: Ctx) -> list[Recommendation]:
    spec = ctx.spec
    if (
        not spec.llm_calls
        or spec.reliability_existing.retries
        or spec.reliability_existing.fallbacks
    ):
        return []
    engines = {str(e.engine.value) for e in spec.endpoints}
    f = ctx.facts("llm_client")
    n = len(spec.llm_calls)
    sites = "The LLM call site goes" if n == 1 else f"All {n} LLM call sites go"
    sdk_retry = any(c.data.get("sdk") in ("openai", "azure_openai", "anthropic") for c in f)
    beyond = " beyond the SDK's built-in retries of failed connections" if sdk_retry else ""
    return [
        Recommendation(
            rule_id="rel.fallback_gateway",
            area=Area.reliability,
            title="Add retry with backoff, and a fallback endpoint through an existing gateway",
            why=(
                f"{sites} to a single endpoint ({', '.join(sorted(engines))}) with no retry policy{beyond} and no "
                "fallback endpoint. A restart of that server fails every in-flight streamed answer, and an outage "
                "fails every request until it recovers."
            ),
            evidence_ids=ctx.ev(*f),
            priority=Priority.P2,
            confidence=0.8,
            verification_method="Chaos benchmark: stop the primary endpoint mid-run; failure rate must stay within the failure SLO.",
            node_keys=[e.key for e in spec.endpoints],
            forge_action=None,
        )
    ]


# ---------------------------------------------------------------------------- evals


@rule
def rag_grounding(ctx: Ctx) -> list[Recommendation]:
    spec = ctx.spec
    if not spec.rag or spec.rag.present.value is not True:
        return []
    out = []
    prompts = ctx.facts("prompt")
    cite_prompt = next((p for p in prompts if CITATION_INSTRUCTION.search(ctx.text_at(p))), None)
    retr = ctx.facts("retriever")
    if cite_prompt:
        out.append(
            Recommendation(
                rule_id="eval.citation_contract",
                area=Area.reliability,
                title="Verify the citation contract the prompt already asks for",
                why=(
                    f"`{cite_prompt.data['name']}` ({cite_prompt.locator.short()}) instructs the model to cite "
                    "retrieved documents, but nothing checks that answers carry citations or that cited ids were "
                    "actually retrieved."
                ),
                evidence_ids=ctx.ev(cite_prompt, *retr),
                priority=Priority.P1,
                confidence=0.85,
                verification_method="Deterministic check `citation_required`: every answer cites at least one id, and cited ids are a subset of the retrieved ids.",
                node_keys=[cite_prompt.key, *[r.key for r in retr]],
                forge_action="eval_citation_required",
            )
        )
    out.append(
        Recommendation(
            rule_id="eval.grounding_judge",
            area=Area.reliability,
            title="Add a calibrated grounding judge for answers built from retrieval",
            why=(
                f"Answers in this app are generated from retrieved documents "
                f"({', '.join(r.locator.short() for r in retr)}). A citation can be present while the claim it "
                "supports is not in the cited text; only a semantic check catches that."
            ),
            evidence_ids=ctx.ev(*retr),
            priority=Priority.P1,
            confidence=spec.rag.present.confidence * 0.9,
            verification_method="Single-failure-mode PASS/FAIL judge (ungrounded_answer), trusted only after TPR and TNR >= 0.8 on human-labeled answers.",
            node_keys=[r.key for r in retr],
            forge_action="eval_grounding_judge",
        )
    )
    return out


@rule
def no_evals(ctx: Ctx) -> list[Recommendation]:
    rel = ctx.spec.reliability_existing
    if rel.evals or not ctx.spec.llm_calls:
        return []
    tests = ctx.facts("test_file")
    tested = ", ".join(sorted({t.locator.path or "" for t in tests})[:3])
    have = (
        f"The repository has {len(tests)} test file{'s' if len(tests) != 1 else ''} ({tested}) but"
        if tests
        else "The repository has no tests,"
    )
    return [
        Recommendation(
            rule_id="eval.regression_suite",
            area=Area.reliability,
            title="Start a regression suite for LLM behaviour",
            why=(
                f"{have} no evaluation framework or eval dataset; "
                "nothing exercises the model's answers, so prompt, model or retrieval changes ship unmeasured."
            ),
            evidence_ids=ctx.ev(*tests),
            priority=Priority.P1,
            confidence=0.85,
            verification_method="Versioned regression dataset run in CI on every PR; failing items block merge.",
            node_keys=[w.key for w in ctx.spec.workflows],
            forge_action="eval_regression_suite",
        )
    ]


# ---------------------------------------------------------------------------- observability


@rule
def tracing_gaps(ctx: Ctx) -> list[Recommendation]:
    rel = ctx.spec.reliability_existing
    otel = [c for c in rel.tracing if "custom log" not in str(c.value)]
    if otel or not ctx.spec.llm_calls:
        return []
    custom = [f for f in ctx.facts("side_effect_function") if f.data["observability_only"]]
    if custom:
        why = (
            f"LLM calls are logged by a custom function (`{custom[0].data['name']}`, {custom[0].locator.short()}) "
            "but records carry no trace id linking a request to its retrieval, prompt version or model version, "
            "so a bad answer cannot be traced back to the change that caused it."
        )
    else:
        why = "No tracing library or call logging was found; a bad answer cannot be traced to its prompt, retrieval or model."
    return [
        Recommendation(
            rule_id="obs.genai_tracing",
            area=Area.observability,
            title="Emit OpenTelemetry GenAI spans with trace id, prompt version and model",
            why=why,
            evidence_ids=ctx.ev(*custom, *ctx.facts("llm_call")),
            priority=Priority.P1,
            confidence=0.85,
            verification_method="Deterministic check on emitted spans: every LLM span has trace_id, gen_ai.request.model, prompt version, token counts.",
            node_keys=[c.key for c in ctx.spec.llm_calls],
            forge_action="add_tracing",
        )
    ]


@rule
def inline_prompt_unversioned(ctx: Ctx) -> list[Recommendation]:
    out = []
    for p in ctx.facts("prompt"):
        if not p.data.get("inline"):
            continue
        out.append(
            Recommendation(
                rule_id="obs.prompt_versioning",
                area=Area.observability,
                title=f"Move `{p.data['name']}` into a versioned prompt file",
                why=(
                    f"`{p.data['name']}` is a {p.data['static_chars']:,}-character string inlined in {p.locator.short()}. "
                    "Edits to it are invisible in traces and eval results, so a quality change cannot be attributed "
                    "to the prompt revision that caused it."
                ),
                evidence_ids=ctx.ev(p),
                priority=Priority.P2,
                confidence=0.95,
                verification_method="Prompt file carries a version header; traces and eval runs record it; a test asserts the code loads that file.",
                node_keys=[p.key],
                forge_action="extract_prompt",
            )
        )
    return out


# ---------------------------------------------------------------------------- inference


@rule
def prefix_cache(ctx: Ctx) -> list[Recommendation]:
    out = []
    serving = ctx.facts("serving_config")
    for s in ctx.facts("system_message"):
        static_tokens = _tokens(s.data["static_chars"])
        prefix_tokens = _tokens(s.data["static_prefix_chars"])
        if s.data["dynamic_head"]:
            segs = ", ".join(d["name"] for d in s.data["dynamic_segments"])
            out.append(
                Recommendation(
                    rule_id="inf.prefix_instability",
                    area=Area.inference,
                    title="Move per-request values out of the start of the system prompt",
                    why=(
                        f"The system message built in `{s.data['function']}` ({s.locator.short()}) starts with runtime "
                        f"values ({segs}) before ~{static_tokens:,} tokens of static text. Every request therefore has a "
                        "unique prefix, so the serving engine's prefix (KV) cache cannot reuse the prefill of the static part."
                    ),
                    evidence_ids=ctx.ev(s),
                    priority=Priority.P0 if static_tokens >= 500 else Priority.P1,
                    confidence=0.9,
                    verification_method="Deterministic prefix-stability test on rendered prompts, then an A/B benchmark: prefix-cache hit rate and p95 TTFT at the fingerprinted concurrency.",
                    node_keys=[s.key],
                    forge_action="prefix_stability_fix",
                )
            )
        elif prefix_tokens >= 512:
            prefix_flag = None
            for sv in serving:
                flags = sv.data["flags"]
                if flags.get("no-enable-prefix-caching"):
                    prefix_flag = (sv, "disabled")
                elif flags.get("enable-prefix-caching"):
                    prefix_flag = (sv, "enabled")
            state = (
                f" The {prefix_flag[0].data['engine']} service `{prefix_flag[0].data['service']}` has prefix caching {prefix_flag[1]}."
                if prefix_flag
                else ""
            )
            out.append(
                Recommendation(
                    rule_id="inf.prefix_stability_guard",
                    area=Area.inference,
                    title="Guard the shared prompt prefix with a regression test",
                    why=(
                        f"Every request starts with the same ~{prefix_tokens:,}-token system prompt (estimated at "
                        f"{CHARS_PER_TOKEN:.0f} chars/token; built in "
                        f"`{s.data['function']}`, {s.locator.short()}), which the serving engine can serve from its "
                        f"prefix cache instead of recomputing.{state} A one-line change that puts a timestamp or "
                        "request id at the top of this prompt would silently throw that away."
                    ),
                    evidence_ids=ctx.ev(s, *(prefix_flag[0:1] if prefix_flag else [])),
                    priority=Priority.P1,
                    confidence=0.85,
                    verification_method="Deterministic test: two rendered requests share >= the static prefix; Guard perf gate on p95 TTFT and prefix-cache hit rate.",
                    node_keys=[s.key, *[sv.key for sv in serving]],
                    forge_action="prefix_stability_test",
                )
            )
    for sv in serving:
        if sv.data["engine"] == "vllm" and sv.data["flags"].get("no-enable-prefix-caching"):
            out.append(
                Recommendation(
                    rule_id="inf.prefix_caching_disabled",
                    area=Area.inference,
                    title="Benchmark re-enabling prefix caching",
                    why=f"`{sv.data['service']}` starts vLLM with --no-enable-prefix-caching ({sv.locator.short()}).",
                    evidence_ids=ctx.ev(sv),
                    priority=Priority.P1,
                    confidence=0.9,
                    verification_method="A/B benchmark on the fingerprinted workload with quality evals as a constraint.",
                    node_keys=[sv.key],
                    forge_action=None,
                )
            )
    return out


@rule
def context_budget(ctx: Ctx) -> list[Recommendation]:
    """Worst-case prompt length vs. the serving context window, from config + prompt sizes."""
    serving = ctx.facts("serving_config")
    systems = ctx.facts("system_message")
    cfg = {c.data["keypath"]: c for c in ctx.facts("config_key")}
    max_ctx_chars = next((c for k, c in cfg.items() if k.endswith("max_context_chars")), None)
    max_tokens = next((c for k, c in cfg.items() if k.endswith("max_tokens")), None)
    top_k = next((c for k, c in cfg.items() if k.endswith("top_k")), None)
    if not (systems and max_ctx_chars):
        return []
    sys_tokens = _tokens(systems[0].data["static_chars"])
    ctx_tokens = _tokens(int(max_ctx_chars.data["value"]))
    gen_tokens = int(max_tokens.data["value"]) if max_tokens else 0
    worst = sys_tokens + ctx_tokens + gen_tokens
    window = None
    sv = next((s for s in serving if s.data["flags"].get("max-model-len")), None)
    if sv:
        window = int(sv.data["flags"]["max-model-len"])
    headroom = (
        f" against a {window:,}-token context window (`--max-model-len` in {sv.locator.short()})"
        if sv and window
        else ""
    )
    over = window is not None and worst > window
    return [
        Recommendation(
            rule_id="inf.context_budget_gate",
            area=Area.inference,
            title="Gate retrieval-size changes on prompt length and TTFT"
            if not over
            else "Worst-case prompt exceeds the serving context window",
            why=(
                f"A request can reach ~{worst:,} tokens (estimated at {CHARS_PER_TOKEN:.0f} chars/token): "
                f"~{sys_tokens:,} system + up to ~{ctx_tokens:,} retrieved context "
                f"(`{max_ctx_chars.data['keypath']}` = {max_ctx_chars.data['value']} chars"
                + (f", `{top_k.data['keypath']}` = {top_k.data['value']}" if top_k else "")
                + f") + {gen_tokens} generated{headroom}. Prefill time grows with prompt length, so raising these values "
                "trades TTFT for recall; today nothing measures that trade."
            ),
            evidence_ids=ctx.ev(
                systems[0],
                max_ctx_chars,
                *([top_k] if top_k else []),
                *([max_tokens] if max_tokens else []),
                *([sv] if sv else []),
            ),
            priority=Priority.P0 if over else Priority.P1,
            confidence=0.8,
            verification_method="Guard perf gate: on PRs touching retrieval config, benchmark the fingerprinted workload and compare p95 TTFT and SLO goodput with the baseline; also run citation/grounding evals.",
            node_keys=[max_ctx_chars.key, *([top_k.key] if top_k else [])],
            forge_action="benchmark_workloads",
        )
    ]


@rule
def no_benchmark_baseline(ctx: Ctx) -> list[Recommendation]:
    spec = ctx.spec
    self_hosted = [
        e for e in spec.endpoints if str(e.engine.value) in ("vllm", "sglang", "ollama", "tgi")
    ]
    if not self_hosted:
        return []
    sv = ctx.facts("serving_config")
    flags = ", ".join(
        f"--{k}={v}"
        for k, v in (sv[0].data["flags"].items() if sv else [])
        if k != "served-model-name"
    )
    return [
        Recommendation(
            rule_id="inf.serving_baseline",
            area=Area.inference,
            title="Record a serving baseline: TTFT, TPOT and SLO goodput by concurrency",
            why=(
                f"The app is served by self-hosted {', '.join(sorted({str(e.engine.value) for e in self_hosted}))}"
                + (f" ({flags})" if flags else "")
                + ", but the repository has no load benchmark, so neither configuration changes nor code changes "
                "that alter prompt length can be compared against a known-good number."
            ),
            evidence_ids=ctx.ev(*sv),
            priority=Priority.P1,
            confidence=0.9,
            verification_method="furnace-bench sweep (c = 1..16) on a workload fingerprinted from traces; report p95 TTFT, TPOT, goodput with CIs.",
            node_keys=[e.key for e in self_hosted],
            forge_action="benchmark_workloads",
        )
    ]


# A finding is resolved when the artifact that verifies it exists in the repository.
# forge_action -> glob of the verifying artifact (relative to the repository root).
VERIFIED_BY: dict[str, str] = {
    "prefix_stability_test": "tests/furnace/test_prompt_prefix.py",
    "security_test_approval_gate": "tests/furnace/test_*_approval.py",
    "eval_citation_required": "evals/run_evals.py",
    "eval_grounding_judge": "evals/judges/ungrounded_answer.yaml",
    "eval_regression_suite": "evals/datasets/*.jsonl",
    "benchmark_workloads": "benchmarks/workloads.yaml",
}


def _verified(rec: Reconstruction, action: str | None) -> bool:
    if action is None or action not in VERIFIED_BY:
        return False
    pattern = VERIFIED_BY[action]
    return any(fnmatch.fnmatchcase(f.path, pattern) for f in rec.inventory.files)


def run_rules(
    rec: Reconstruction, fact_uuid: dict[str, Any] | None = None, *, include_resolved: bool = False
) -> list[Recommendation]:
    """Evaluate every rule. Findings whose verifying artifact is already present in the
    repository are dropped unless include_resolved=True."""
    ctx = Ctx(rec=rec, fact_uuid=fact_uuid or {})
    recs: list[Recommendation] = []
    for r in RULES:
        recs.extend(r(ctx))
    if not include_resolved:
        recs = [r for r in recs if not _verified(rec, r.forge_action)]
    order = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2}
    recs.sort(key=lambda x: (order[x.priority], -x.confidence))
    return recs
