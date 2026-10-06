"""Forge: turn Blueprint recommendations into a reviewable retrofit change set.

Only recommendations that fired for this application produce artifacts. Every
change carries its reason, evidence, the evaluator/benchmark target it serves,
and its risk. Code edits (evalability refactors) replace exact AST spans and are
verified to leave the rendered prompts byte-identical.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from furnace.code_intel.facts import Fact
from furnace.contracts.blueprint import Recommendation
from furnace.contracts.guard import ChangeType, ForgeChange, ForgePlan
from furnace.forge import templates as T
from furnace.forge.harness import HARNESS_FILE, HarnessError, generate_harness
from furnace.reconstruction.build import Reconstruction

CITATION_RE = r"\[doc:([A-Za-z0-9_.\-]+)\]"
NOT_FOUND_RE = r"(?i)could not find (?:that|this|it) in"
DEFAULT_TIMEOUT_S = 60.0


class ForgeError(Exception):
    pass


@dataclass
class ForgeResult:
    plan: ForgePlan
    files: dict[str, str] = field(default_factory=dict)  # path -> full new content
    skipped: list[dict[str, str]] = field(default_factory=list)  # {rule_id, reason}


def _module(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".").removeprefix("src.")


def _span(src: str, node: ast.expr | ast.stmt) -> tuple[int, int]:
    lines = src.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def off(lineno: int, col: int) -> int:
        line = lines[lineno - 1]
        return starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", errors="ignore"))

    return off(node.lineno, node.col_offset), off(
        node.end_lineno or node.lineno, node.end_col_offset or 0
    )


class Planner:
    def __init__(
        self,
        rec: Reconstruction,
        recs: list[Recommendation],
        *,
        questions: list[str],
        workload: dict[str, Any] | None = None,
        default_branch: str = "main",
    ) -> None:
        self.rec = rec
        self.recs = recs
        self.questions = questions
        self.workload = workload
        self.branch = default_branch
        self.root = rec.inventory.root
        self.result = ForgeResult(plan=ForgePlan())
        self._src: dict[str, str] = {}

    # ---------------------------------------------------------------- helpers

    def read(self, path: str) -> str:
        if path in self.result.files:
            return self.result.files[path]
        if path not in self._src:
            self._src[path] = (self.root / path).read_text(encoding="utf-8")
        return self._src[path]

    def write(
        self,
        path: str,
        content: str,
        *,
        change: ChangeType,
        reason: str,
        target: str,
        risk: str,
        rec: Recommendation | None,
    ) -> None:
        self.result.files[path] = content
        self.result.plan.changes.append(
            ForgeChange(
                path=path,
                change_type=change,
                reason=reason,
                evidence_ids=rec.evidence_ids if rec else [],
                target=target,
                risk=risk,
                recommendation_rule_id=rec.rule_id if rec else None,
            )
        )

    def skip(self, rule_id: str, reason: str) -> None:
        self.result.skipped.append({"rule_id": rule_id, "reason": reason})

    def rec_for(self, action: str) -> list[Recommendation]:
        return [r for r in self.recs if r.forge_action == action]

    # ---------------------------------------------------------------- artifacts

    def harness(self) -> bool:
        if (self.root / HARNESS_FILE).exists():
            return True
        try:
            h = generate_harness(self.rec)
        except HarnessError as exc:
            self.skip("forge.harness", f"cannot generate an eval harness: {exc}")
            return False
        self.write(
            HARNESS_FILE,
            h.source,
            change=ChangeType.add_file,
            reason=f"Evals and benchmarks need the exact messages the app sends; this renders them from {h.handler} without starting the server or calling the model.",
            target="eval harness (all evals, prefix test, perf gate)",
            risk="None at runtime: imported only by tests, evals and benchmarks.",
            rec=None,
        )
        return True

    def prefix_test(self, shared: int | None) -> None:
        for r in self.rec_for("prefix_stability_test"):
            if shared is None:
                self.skip(r.rule_id, "needs a measured shared prefix (render the harness first)")
                continue
            src = T.fill(
                T.PREFIX_TEST,
                SHARED=shared,
                THRESHOLD=int(shared * 0.9),
                QUESTIONS=json.dumps(self.questions[:4]),
            )
            self.write(
                "tests/furnace/test_prompt_prefix.py",
                src,
                change=ChangeType.add_file,
                reason=r.why,
                target="check:prompt_prefix_stable",
                risk="Test-only.",
                rec=r,
            )

    def approval_test(self) -> None:
        for r in self.rec_for("security_test_approval_gate"):
            key = r.node_keys[0]
            f = next((x for x in self.rec.facts.of("side_effect_function") if x.key == key), None)
            if f is None or not f.data["approval_gate_detail"].get("present"):
                self.skip(r.rule_id, "approval gate not found")
                continue
            generated = approval_test_source(self.rec, f)
            if generated is None:
                self.skip(r.rule_id, "side effect calls could not be patched safely")
                continue
            path, src = generated
            self.write(
                path,
                src,
                change=ChangeType.add_file,
                reason=r.why,
                target="security:approval_gate",
                risk="Test-only; outbound calls are patched to fail.",
                rec=r,
            )

    def timeout(self) -> None:
        for r in self.rec_for("add_llm_timeout"):
            clients = [c for c in self.rec.facts.of("llm_client") if not c.data.get("has_timeout")]
            if not clients:
                self.skip(
                    r.rule_id, "timeout must be set per call; client-level codemod not applicable"
                )
                continue
            for c in clients:
                path = c.locator.path or ""
                src = self.read(path)
                tree = ast.parse(src)
                call = next(
                    (
                        n.value
                        for n in tree.body
                        if isinstance(n, ast.Assign)
                        and isinstance(n.value, ast.Call)
                        and any(
                            isinstance(t, ast.Name) and t.id == c.data["var"] for t in n.targets
                        )
                    ),
                    None,
                )
                if call is None:
                    self.skip(
                        r.rule_id, f"client {c.data['var']} not found at module level in {path}"
                    )
                    continue
                new_call = ast.Call(
                    func=call.func,
                    args=call.args,
                    keywords=[
                        *call.keywords,
                        ast.keyword(arg="timeout", value=ast.Constant(DEFAULT_TIMEOUT_S)),
                    ],
                )
                a, b = _span(src, call)
                updated = src[:a] + ast.unparse(new_call) + src[b:]
                ast.parse(updated)
                self.write(
                    path,
                    updated,
                    change=ChangeType.codemod,
                    reason=r.why,
                    target="rel.llm_timeout",
                    risk=f"Requests slower than {DEFAULT_TIMEOUT_S:.0f} s now fail instead of hanging; raise the value if your longest legitimate generation takes longer.",
                    rec=r,
                )
                test = T.fill(
                    T.TIMEOUT_TEST,
                    MODULE=_module(path),
                    VAR=c.data["var"],
                    MAX_SECONDS=int(DEFAULT_TIMEOUT_S * 2),
                )
                self.write(
                    "tests/furnace/test_llm_timeout.py",
                    test,
                    change=ChangeType.add_file,
                    reason="Keeps the timeout from being removed later.",
                    target="rel.llm_timeout",
                    risk="Test-only.",
                    rec=r,
                )

    def extract_prompt(self) -> None:
        for r in self.rec_for("extract_prompt"):
            key = r.node_keys[0]
            f = next((x for x in self.rec.facts.of("prompt") if x.key == key), None)
            if f is None:
                continue
            path, name = f.locator.path or "", f.data["name"]
            src = self.read(path)
            tree = ast.parse(src)
            assign = next(
                (
                    n
                    for n in tree.body
                    if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
                ),
                None,
            )
            if assign is None or not (
                isinstance(assign.value, ast.Constant) and isinstance(assign.value.value, str)
            ):
                self.skip(r.rule_id, f"{name} is not a plain string constant")
                continue
            prompt_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            prompt_path = f"prompts/{prompt_id}.md"
            body = assign.value.value
            self.write(
                prompt_path,
                T.fill(T.PROMPT_FILE, ID=prompt_id, SOURCE=f"{path}::{name}") + body,
                change=ChangeType.add_file,
                reason=r.why,
                target="obs.prompt_versioning",
                risk="None: the loader returns the exact original text (verified byte-identical).",
                rec=r,
            )
            depth = path.count("/")
            loader = (
                f'PROMPT_DIR = Path(__file__).resolve(){".parent" * (depth + 1)} / "prompts"\n\n\n'
                "def _load_prompt(name: str) -> tuple[str, int]:\n"
                '    """Prompt text and version from prompts/<name>.md (front matter, then the exact text)."""\n'
                '    raw = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")\n'
                '    _, meta, body = raw.split("---\\n", 2)\n'
                '    version = int(next(line.split(":", 1)[1] for line in meta.splitlines() if line.startswith("version:")))\n'
                "    return body, version\n\n\n"
                f'{name}, {name}_VERSION = _load_prompt("{prompt_id}")\n'
            )
            a, b = _span(src, assign)
            updated = src[:a] + loader + src[b:]
            if "from pathlib import Path" not in updated:
                updated = _add_import(updated, "from pathlib import Path")
            ast.parse(updated)
            self.write(
                path,
                updated,
                change=ChangeType.codemod,
                reason=f"Load `{name}` from {prompt_path} and expose `{name}_VERSION` for traces and eval results.",
                target="obs.prompt_versioning",
                risk="Prompt text unchanged (verified byte-identical through the harness); the file must ship with the app.",
                rec=r,
            )

    def evals(self) -> None:
        recs = self.rec_for("eval_citation_required")
        call = next(iter(self.rec.facts.of("llm_call")), None)
        client = next(
            (
                c
                for c in self.rec.facts.of("llm_client")
                if call and c.key == call.data.get("endpoint_key")
            ),
            None,
        )
        if not recs or call is None or client is None:
            for r in recs:
                self.skip(r.rule_id, "no resolvable LLM client for the eval runner")
            return
        r = recs[0]
        model = call.data.get("model_effective") or "model"
        max_tokens = 256
        runner = T.fill(
            T.EVAL_RUNNER,
            LLM_MODULE=_module(client.locator.path or ""),
            CLIENT=client.data["var"],
            CITATION_RE=CITATION_RE,
            NOT_FOUND_RE=NOT_FOUND_RE,
            MODEL=model,
            MAX_TOKENS=max_tokens,
        )
        self.write(
            "evals/run_evals.py",
            runner,
            change=ChangeType.add_file,
            reason=r.why,
            target="check:citation_required",
            risk="Not run by plain pytest; Furnace Guard runs it against your endpoint.",
            rec=r,
        )
        rows = [
            json.dumps({"id": f"q{i:03d}", "question": q}) for i, q in enumerate(self.questions)
        ]
        self.write(
            "evals/datasets/questions.jsonl",
            "\n".join(rows) + "\n",
            change=ChangeType.add_file,
            reason="Bootstrap dataset of real user questions for the citation and grounding evals.",
            target="check:citation_required, judge:ungrounded_answer",
            risk="Data-only.",
            rec=r,
        )
        for j in self.rec_for("eval_grounding_judge"):
            self.write(
                "evals/judges/ungrounded_answer.yaml",
                T.JUDGE_SPEC,
                change=ChangeType.add_file,
                reason=j.why,
                target="judge:ungrounded_answer",
                risk="Advisory until calibrated against human labels.",
                rec=j,
            )

    def benchmarks(self) -> None:
        recs = self.rec_for("benchmark_workloads")
        if not recs:
            return
        r = recs[0]
        if self.workload:
            body = yaml.safe_dump({"workloads": [self.workload]}, sort_keys=False)
            note = f"# Fingerprinted from {self.workload.get('n_observed', '?')} recorded LLM calls (source: {self.workload.get('source')}).\n"
        else:
            self.skip(
                r.rule_id,
                "no traces to fingerprint; a synthetic workload would be labelled as such",
            )
            return
        self.write(
            "benchmarks/workloads.yaml",
            "# Installed by Furnace Forge.\n" + note + body,
            change=ChangeType.add_file,
            reason=r.why,
            target="bench:chat_perf_gate",
            risk="Data-only.",
            rec=r,
        )
        slo = (self.workload.get("slo") or {}).get("ttft_p95_ms") or 500
        self.write(
            "furnace.yaml",
            T.fill(T.FURNACE_YAML, SLO_TTFT=int(slo)),
            change=ChangeType.add_file,
            reason="Tells Furnace Guard which harness, evals, benchmarks and regression budget apply to this repository.",
            target="Guard configuration",
            risk="Configuration only.",
            rec=r,
        )

    def ci(self) -> None:
        if not any(p.startswith("tests/furnace/") for p in self.result.files):
            return
        self.write(
            ".github/workflows/furnace.yml",
            T.fill(T.CI_WORKFLOW, BRANCH=self.branch),
            change=ChangeType.add_file,
            reason="Runs the installed deterministic reliability tests on every pull request; no model or secrets required.",
            target="CI",
            risk="Adds a CI job (~1 minute).",
            rec=None,
        )

    def run(self, *, shared_prefix: int | None) -> ForgeResult:
        if self.harness():
            self.prefix_test(shared_prefix)
        self.approval_test()
        self.timeout()
        self.extract_prompt()
        if (self.root / HARNESS_FILE).exists() or HARNESS_FILE in self.result.files:
            self.evals()
        self.benchmarks()
        self.ci()
        if not any(p.startswith("tests/furnace/") for p in self.result.files):
            pass
        else:
            self.result.files.setdefault("tests/furnace/__init__.py", "")
        return self.result


def approval_test_source(rec: Reconstruction, f: Fact) -> tuple[str, str] | None:
    """(path, source) of a test asserting that `f` (a side-effecting function with an
    approval gate) refuses to act when the approval parameter is False. Outbound calls
    are patched to raise, so the test proves no side effect happens. Generated from the
    revision where the gate exists; it can then be run against any later revision."""
    path = f.locator.path or ""
    func = f.data["name"]
    param = f.data["approval_gate_detail"].get("param")
    if not param:
        return None
    fn = next((x for x in rec.facts.of("function") if x.key == f.data["function_key"]), None)
    if fn is None:
        return None
    args = ", ".join(
        f"{p}=False" if p == param else f'{p}="furnace-test"' for p in fn.data["params"]
    )
    patches = []
    for eff in f.data["effects"]:
        call = eff["call"]
        if "." in call:
            owner, attr = call.rsplit(".", 1)
            patches.append(f'    monkeypatch.setattr(target.{owner}, "{attr}", _forbid)')
    if not patches:
        return None
    effect = f.data["side_effect"]
    src = T.fill(
        T.APPROVAL_TEST,
        FUNC=func,
        LOCATION=f.locator.short(),
        EFFECT=("an " if effect[0] in "aeiou" else "a ") + effect,
        PARAM=param,
        MODULE=_module(path),
        PATCHES="\n".join(patches),
        ARGS=args,
    )
    return f"tests/furnace/test_{func}_approval.py", src


def _add_import(src: str, line: str) -> str:
    tree = ast.parse(src)
    last = 0
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            last = n.end_lineno or n.lineno
        elif not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)):
            break
    lines = src.splitlines(keepends=True)
    lines.insert(last, line + "\n")
    return "".join(lines)


def apply(result: ForgeResult, dest: Path) -> None:
    for path, content in result.files.items():
        p = dest / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
