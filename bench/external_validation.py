"""Generalization beyond call sites: Scan, Forge and Guard on independent applications.

  uv run python bench/external_validation.py [--sandbox]

Apps: held-out set 4 (bench/ground_truth/*.yaml with split held-out-4), labeled and
committed before this script first ran. RQ1 (bench/rq1.py) scores the reconstruction
against those labels; this script checks what RQ1 does not:

1. Source links: every Blueprint finding's evidence resolves to an existing file and line
   range whose text contains the evidence excerpt.
2. Forge: the change set plans on the app as it is; with --sandbox it is also validated
   (prompts byte-identical through the harness, installed and existing tests in the
   sandbox), exactly as `furnace gh-forge` does before opening a PR.
3. Guard impact: three synthetic pull requests applied to the real source (a per-request
   value prepended to the system prompt; a docs-only change; an unrelated code change),
   analyzed against a generic suite (the kinds of checks Forge installs). Expected
   selections are the CORRECT behavior, fixed in EXPECTED below before the first run,
   not a prediction of what Furnace does.
4. Repair applicability: for the prompt scenario, whether the supported regression
   signature is detected and whether each deterministic strategy produces an edit that
   parses and makes the system prompt prefix-stable again (re-analyzed, not executed).

Synthetic PRs are labeled as synthetic in the report. Nothing here talks to GitHub or an
LLM. Output: bench/results/<date>/external_validation.{json,md}
"""

from __future__ import annotations

import argparse
import ast
import shutil
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

import yaml
from common import EXTERNAL, GROUND_TRUTH, manifest, md_table, results_dir, write_json
from furnace.blueprint.rules import run_rules
from furnace.forge.planner import Planner
from furnace.guardian.impact import SuiteItem, analyze_impact, analyze_tree
from furnace.guardian.repair.signatures import prefix_instability_node, supported_signatures
from furnace.guardian.repair.strategies import STRATEGIES, StrategyError
from furnace.reconstruction.build import Builder, Reconstruction, collect_facts

QUALITY = {
    "prompt",
    "retrieval_config",
    "retrieval",
    "model",
    "llm_call",
    "generation_config",
    "endpoint",
    "llm_sdk",
}
PERF = {
    "prompt",
    "retrieval_config",
    "retrieval",
    "serving_config",
    "model",
    "llm_call",
    "endpoint",
    "generation_config",
}
GENERIC_SUITE = [
    SuiteItem("unit:existing_tests", "unit", ["component:*"], {"code", "dependency"}),
    SuiteItem("check:prompt_prefix_stable", "check", ["prompt:*"], {"prompt"}),
    SuiteItem("check:answer_quality", "check", ["capability:*"], QUALITY),
    SuiteItem("bench:perf_gate", "benchmark", ["workflow:*"], PERF),
]
QUESTIONS = ["What can you help me with?", "How do I get started?", "What does it cost?"]

# Synthetic pull requests: (file, old, new, imports to add after the first import line).
# `old` must occur in the pinned source; the first occurrence is replaced.
EDITS: dict[str, dict[str, tuple[str, str, str, str]]] = {
    "openai-chat-backend-fastapi": {
        "prompt_dynamic_head": (
            "src/api/chat.py",
            '[{"role": "system", "content": SYSTEM_PROMPT}]',
            '[{"role": "system", "content": f"Request {uuid.uuid4()} at {time.time()}\\n" + SYSTEM_PROMPT}]',
            "import time\nimport uuid\n",
        ),
        "docs_only": (
            "README.md",
            "\n",
            "\nThis line was added by a synthetic docs-only change.\n",
            "",
        ),
        "code_unrelated": (
            "src/api/__init__.py",
            '"http://localhost:8080"',
            '"http://localhost:8081"',
            "",
        ),
    },
    "tech-trends-chatbot": {
        "prompt_dynamic_head": (
            "backend/app/assistants/assistant.py",
            "{'role': 'system', 'content': MAIN_SYSTEM_PROMPT}",
            "{'role': 'system', 'content': f'Chat {chat_id} at {time()}\\n' + MAIN_SYSTEM_PROMPT}",
            "",
        ),
        "docs_only": (
            "README.md",
            "\n",
            "\nThis line was added by a synthetic docs-only change.\n",
            "",
        ),
        "code_unrelated": ("backend/app/main.py", "return 'ok'", "return 'healthy'", ""),
    },
    "rag-postgres-openai-python": {
        "prompt_dynamic_head": (
            "src/backend/fastapi_app/rag_simple.py",
            "instructions=self.answer_prompt_template,",
            'instructions=f"Request {uuid.uuid4()}\\n" + self.answer_prompt_template,',
            "import uuid\n",
        ),
        "docs_only": (
            "README.md",
            "\n",
            "\nThis line was added by a synthetic docs-only change.\n",
            "",
        ),
        "code_unrelated": (
            "src/backend/fastapi_app/routes/frontend_routes.py",
            '"static/favicon.ico"',
            '"static/favicon.png"',
            "",
        ),
    },
}
# The correct Guard behavior per scenario (identical for every app).
EXPECTED: dict[str, dict[str, Any]] = {
    "prompt_dynamic_head": {
        "must_select": {"check:prompt_prefix_stable", "bench:perf_gate"},
        "signature": ["prefix_instability"],
    },
    "docs_only": {
        "must_select": set(),
        "must_not_select": {
            "check:prompt_prefix_stable",
            "check:answer_quality",
            "bench:perf_gate",
            "unit:existing_tests",
        },
        "signature": [],
    },
    "code_unrelated": {
        "must_select": set(),
        "must_not_select": {
            "check:prompt_prefix_stable",
            "check:answer_quality",
            "bench:perf_gate",
        },
        "signature": [],
    },
}


def held_out_4() -> list[dict[str, Any]]:
    out = []
    for gt in sorted(GROUND_TRUTH.glob("*.yaml")):
        spec = yaml.safe_load(gt.read_text(encoding="utf-8"))
        if spec.get("split") == "held-out-4":
            out.append(
                {"app": spec["app"], "root": EXTERNAL / spec["app"], "commit": spec["commit"]}
            )
    return out


# ------------------------------------------------------------------------ 1. source links


def scan(root: Path) -> tuple[Reconstruction, list[Any], dict[str, Any]]:
    t0 = time.monotonic()
    inv, facts = collect_facts(root)
    fact_uuid = {f.id: uuid.uuid5(uuid.NAMESPACE_URL, f"{root.name}:{f.id}") for f in facts.facts}
    b = Builder(inv, facts, fact_uuid)
    spec, graph = b.build()
    rec = Reconstruction(inventory=inv, facts=facts, claims=b.claims, appspec=spec, graph=graph)
    recs = run_rules(rec, fact_uuid)
    by_uuid = {fact_uuid[f.id]: f for f in facts.facts}
    checked, broken, file_level = 0, [], 0
    for r in recs:
        for eid in r.evidence_ids:
            f = by_uuid.get(eid)
            if f is None:
                broken.append(f"{r.rule_id}: evidence {eid} has no fact")
                continue
            loc = f.locator
            if not loc.path:
                continue  # non-file evidence (none expected for repo scans)
            checked += 1
            p = root / loc.path
            if not p.is_file():
                broken.append(f"{r.rule_id}: {loc.path} does not exist")
                continue
            if (f.excerpt or "").strip() == loc.path:
                file_level += 1
                continue  # file-level evidence ("this file exists"): existence was checked
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            lo, hi = (loc.line_start or 1), (loc.line_end or loc.line_start or len(lines))
            if lo < 1 or hi > len(lines) or lo > hi:
                broken.append(
                    f"{r.rule_id}: {loc.path}:{lo}-{hi} outside the file ({len(lines)} lines)"
                )
                continue
            window = " ".join("\n".join(lines[max(0, lo - 2) : hi + 1]).split())
            needle = " ".join((f.excerpt or "").split())[:60]
            if needle and needle not in window:
                broken.append(f"{r.rule_id}: excerpt not at {loc.path}:{lo}-{hi}: {needle[:40]!r}")
    kinds: dict[str, int] = {}
    for f in facts.facts:
        kinds[f.kind] = kinds.get(f.kind, 0) + 1
    stats = {
        "seconds": round(time.monotonic() - t0, 2),
        "python_files": sum(1 for x in inv.files if x.path.endswith(".py")),
        "llm_call_facts": kinds.get("llm_call", 0),
        "routes": kinds.get("route", 0),
        "findings": len(recs),
        "findings_by_rule": sorted({r.rule_id for r in recs}),
        "evidence_checked": checked,
        "evidence_file_level": file_level,  # checked for existence only
        "evidence_broken": broken,
    }
    return rec, recs, stats


# ------------------------------------------------------------------------ 2. Forge


def forge(rec: Reconstruction, recs: list[Any], root: Path, sandbox: bool) -> dict[str, Any]:
    try:
        result = Planner(rec, recs, questions=QUESTIONS).run(shared_prefix=None)
    except Exception as exc:  # a planner crash is a finding
        return {
            "planned": False,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc()[-1500:],
        }
    out: dict[str, Any] = {
        "planned": True,
        "files": sorted(result.files),
        "skipped": [
            {"rule_id": s.get("rule_id"), "reason": s.get("reason")} for s in result.skipped
        ],
    }
    if sandbox:
        from furnace.forge.validate import validate

        try:
            v = validate(root, result, QUESTIONS)
            out["validation"] = {**v.as_dict(), "ok": v.ok}
        except Exception as exc:
            out["validation"] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:800]}"}
    return out


# ------------------------------------------------------------------------ 3-4. Guard + repair


def apply_edit(root: Path, edit: tuple[str, str, str, str]) -> None:
    path, old, new, imports = edit
    p = root / path
    src = p.read_text(encoding="utf-8")
    if old not in src:
        raise ValueError(f"synthetic edit target not found in {path}: {old[:50]!r}")
    src = src.replace(old, new, 1)
    if imports:
        lines = src.splitlines(keepends=True)
        first = next(i for i, ln in enumerate(lines) if ln.startswith(("import ", "from ")))
        lines.insert(first, imports)
        src = "".join(lines)
    p.write_text(src, encoding="utf-8")


def guard(app: str, root: Path, base_state: Any) -> list[dict[str, Any]]:
    out = []
    for scenario, edit in EDITS[app].items():
        tmp = Path(tempfile.mkdtemp(prefix="extval-"))
        try:
            head = Path(
                shutil.copytree(
                    root, tmp / "head", ignore=shutil.ignore_patterns(".git", "node_modules")
                )
            )
            apply_edit(head, edit)
            head_state = analyze_tree(head)
            imp = analyze_impact(base_state, head_state, GENERIC_SUITE)
            selected = {s.key for s in imp.impact.selected}
            sigs = supported_signatures(imp)
            exp = EXPECTED[scenario]
            missing = sorted(exp["must_select"] - selected)
            extra = sorted(selected & exp.get("must_not_select", set()))
            row: dict[str, Any] = {
                "scenario": scenario,
                "synthetic": True,
                "file": edit[0],
                "changed": [c.path for c in imp.impact.changed],
                "categories": sorted(imp.categories),
                "selected": sorted(selected),
                "fell_back_to_full": imp.impact.fell_back_to_full,
                "signatures": sigs,
                "missing": missing,
                "unexpected": extra,
                "signature_ok": sigs == exp["signature"],
                "correct": not missing and not extra and sigs == exp["signature"],
            }
            if scenario == "prompt_dynamic_head":
                row["repair"] = repair_applicability(head, imp)
            out.append(row)
        except Exception as exc:
            out.append(
                {
                    "scenario": scenario,
                    "synthetic": True,
                    "error": f"{type(exc).__name__}: {exc}",
                    "correct": False,
                }
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def repair_applicability(head: Path, imp: Any) -> dict[str, Any]:
    node = prefix_instability_node(imp)
    if node is None:
        return {"signature_detected": False}
    sys_path, fn_part = node.node_key.removeprefix("prompt:").split("::", 1)
    function = fn_part.removesuffix("#system")
    src = (head / sys_path).read_text(encoding="utf-8")
    results = {}
    for name, strategy in STRATEGIES.items():
        try:
            edit = strategy(sys_path, src, function)
        except StrategyError as exc:
            results[name] = {"applicable": False, "reason": str(exc)}
            continue
        try:
            ast.parse(edit.after)
        except SyntaxError as exc:
            results[name] = {"applicable": True, "parses": False, "reason": str(exc)}
            continue
        tmp = Path(tempfile.mkdtemp(prefix="extval-fix-"))
        try:
            fixed = Path(shutil.copytree(head, tmp / "fixed"))
            (fixed / sys_path).write_text(edit.after, encoding="utf-8")
            st = analyze_tree(fixed)
            n = next((x for x in st.graph.nodes if x.key == node.node_key), None)
            stable = n is not None and not (n.attrs or {}).get("dynamic_head", False)
            results[name] = {"applicable": True, "parses": True, "prefix_stable_after": stable}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return {"signature_detected": True, "node": node.node_key, "strategies": results}


# ------------------------------------------------------------------------ report


def render(res: dict[str, Any]) -> str:
    lines = [
        "# External validation (held-out set 4): Scan, Forge, Guard, repair",
        "",
        "Apps labeled and committed before this script first ran; Guard scenarios are "
        "synthetic edits applied to the real source; expected selections are the correct "
        "behavior, fixed before the run. RQ1 scores call sites, models and routes on the same "
        "apps (rq1.md).",
        "",
        "## Scan: findings link to real source",
        "",
        md_table(
            [
                "app",
                "py files",
                "scan s",
                "findings",
                "evidence checked",
                "of which file-existence only",
                "broken links",
            ],
            [
                [
                    a["app"],
                    a["scan"]["python_files"],
                    a["scan"]["seconds"],
                    a["scan"]["findings"],
                    a["scan"]["evidence_checked"],
                    a["scan"].get("evidence_file_level", "n/a"),
                    len(a["scan"]["evidence_broken"]),
                ]
                for a in res["apps"]
            ],
        ),
        "",
        "## Forge",
        "",
        md_table(
            ["app", "planned", "files", "skipped", "sandbox validation"],
            [
                [
                    a["app"],
                    a["forge"].get("planned"),
                    len(a["forge"].get("files", [])),
                    len(a["forge"].get("skipped", [])),
                    _val(a["forge"].get("validation")),
                ]
                for a in res["apps"]
            ],
        ),
        "",
        "## Guard impact on synthetic PRs (generic suite)",
        "",
        md_table(
            ["app", "scenario", "categories", "selected", "signature", "correct", "why not"],
            [
                [
                    a["app"],
                    g["scenario"],
                    ", ".join(g.get("categories", [])) or "–",
                    ", ".join(g.get("selected", [])) or "none",
                    ", ".join(g.get("signatures", [])) or "–",
                    "yes" if g["correct"] else "NO",
                    g.get("error")
                    or "; ".join(
                        [f"missing {', '.join(g['missing'])}"] * bool(g.get("missing"))
                        + [f"unexpected {', '.join(g['unexpected'])}"] * bool(g.get("unexpected"))
                        + ["signature"] * (not g.get("signature_ok", True))
                    )
                    or "",
                ]
                for a in res["apps"]
                for g in a["guard"]
            ],
        ),
        "",
        "## Repair applicability (prompt scenario)",
        "",
    ]
    for a in res["apps"]:
        g = next((x for x in a["guard"] if x["scenario"] == "prompt_dynamic_head"), {})
        r = g.get("repair") or {}
        if not r.get("signature_detected"):
            lines.append(f"- {a['app']}: signature not detected; repair not attempted")
            continue
        parts = [
            f"{k.split('.')[-1]}: "
            + (
                "prefix-stable after edit"
                if v.get("prefix_stable_after")
                else f"not applicable ({v.get('reason', 'still dynamic')})"
            )
            for k, v in r["strategies"].items()
        ]
        lines.append(f"- {a['app']} ({r['node']}): " + "; ".join(parts))
    broken = [(a["app"], b) for a in res["apps"] for b in a["scan"]["evidence_broken"]]
    if broken:
        lines += ["", "## Broken evidence links", "", *[f"- {app}: {b}" for app, b in broken]]
    return "\n".join(lines) + "\n"


def _val(v: dict[str, Any] | None) -> str:
    if v is None:
        return "not run (--sandbox)"
    if "error" in v:
        return f"error: {v['error'][:120]}"
    return (
        f"ok={v.get('ok')} prompts_identical={v.get('prompts_identical')} "
        f"installed={v.get('installed_tests')} existing={v.get('existing_tests')}"
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--sandbox", action="store_true", help="also validate Forge in the Docker sandbox"
    )
    a = p.parse_args()
    apps = []
    for app in held_out_4():
        root = app["root"]
        print(f"== {app['app']}", flush=True)
        rec, recs, stats = scan(root)
        print(
            f"   scan: {stats['findings']} findings, {len(stats['evidence_broken'])} broken links",
            flush=True,
        )
        fg = forge(rec, recs, root, a.sandbox)
        print(f"   forge: planned={fg.get('planned')} files={len(fg.get('files', []))}", flush=True)
        base_state = analyze_tree(root)
        gd = guard(app["app"], root, base_state)
        print(
            "   guard: "
            + ", ".join(f"{g['scenario']}={'ok' if g['correct'] else 'NO'}" for g in gd),
            flush=True,
        )
        apps.append({**app, "root": str(root), "scan": stats, "forge": fg, "guard": gd})
    res = {
        "manifest": manifest(),
        "expected": {
            k: {kk: sorted(vv) if isinstance(vv, set) else vv for kk, vv in v.items()}
            for k, v in EXPECTED.items()
        },
        "apps": apps,
    }
    out = results_dir()
    write_json(out / "external_validation.json", res)
    (out / "external_validation.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
