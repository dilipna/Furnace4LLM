"""Render Guard results as a GitHub check run (title, summary, annotations) and
repair results as a draft pull request body."""

from __future__ import annotations

from typing import Any

from furnace.guardian.execute import ItemResult
from furnace.guardian.impact import ImpactResult

ICON = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "skip": "SKIP", "error": "ERROR"}
GROUPS = [
    ("Quality", ("check:citation_required", "judge:")),
    ("Performance", ("bench:", "check:context_budget", "check:prompt_prefix_stable")),
    ("Security", ("security:",)),
    ("Tests", ("unit:",)),
]


def _group(key: str) -> str:
    for name, prefixes in GROUPS:
        if key.startswith(prefixes):
            return name
    return "Other"


def check_run(impact: ImpactResult, results: list[ItemResult], conclusion: str) -> dict[str, Any]:
    imp = impact.impact
    failed = [r for r in results if r.verdict == "fail"]
    title = (
        f"{len(failed)} regression{'s' if len(failed) != 1 else ''} found: "
        + ", ".join(r.key.split(":", 1)[1] for r in failed)
        if failed
        else f"No regressions in {len(results)} targeted check{'s' if len(results) != 1 else ''}"
    )
    lines = [
        f"**Ran {len(imp.selected)} of {imp.full_suite_size} suite items** selected from the behavior-to-code graph"
        + (" (full suite: unmapped change)" if imp.fell_back_to_full else "")
        + f". Change categories: {', '.join(sorted(impact.categories)) or 'none'}.",
        "",
    ]
    for group, _ in [*GROUPS, ("Other", ())]:
        rows = [r for r in results if _group(r.key) == group]
        if not rows:
            continue
        lines += [f"### {group}", "", "| check | result | detail |", "|---|---|---|"]
        lines += [f"| `{r.key}` | **{ICON[r.verdict]}** | {r.detail} |" for r in rows]
        lines.append("")
    if imp.skipped:
        lines += ["<details><summary>Not run for this change</summary>", ""]
        lines += [f"- `{s.key}`: {s.reason}" for s in imp.skipped]
        lines += ["", "</details>"]
    touched = [t for t in imp.touched if t.attr_changes]
    text = ["### What changed in the graph", ""]
    for t in touched[:20]:
        changes = "; ".join(
            f"`{k}` {v[0]!r} -> {v[1]!r}"
            for k, v in t.attr_changes.items()
            if k not in ("dynamic_segments",)
        )
        text.append(f"- `{t.node_key}`: {changes}")
    annotations = []
    for r in failed:
        if r.key in ("check:prompt_prefix_stable", "bench:chat_perf_gate"):
            for cf in imp.changed:
                for h in cf.hunks:
                    if any(t.node_key.startswith(f"prompt:{cf.path}") for t in imp.touched):
                        annotations.append(
                            {
                                "path": cf.path,
                                "start_line": h.new_start,
                                "end_line": h.new_start + max(h.new_lines, 1) - 1,
                                "annotation_level": "failure",
                                "message": r.detail,
                                "title": r.key,
                            }
                        )
    return {
        "conclusion": conclusion,
        "title": title[:250],
        "summary": "\n".join(lines),
        "text": "\n".join(text),
        "annotations": annotations[:50],
    }


def repair_pr_body(attempt: Any, perf: dict[str, Any], explanation: str, test_path: str) -> str:
    rows = []
    for name, key in (("PR head", "head_vs_base"), ("This repair", "candidate_vs_base")):
        c = perf.get(key) or {}
        if c:
            hits = c.get("prefix_hit_rate") or (None, None)
            rows.append(
                f"| {name} | {c.get('baseline')} ms | {c.get('value')} ms | {c.get('change_pct'):+} % | "
                + (f"{hits[1] * 100:.0f}%" if hits[1] is not None else "–")
                + f" | {c.get('verdict')} |"
            )
    perf_table = (
        "\n".join(
            [
                "| revision | base p95 TTFT | p95 TTFT | change | prefix-cache hit | gate |",
                "|---|---:|---:|---:|---:|---|",
                *rows,
            ]
        )
        if rows
        else "_No performance run attached._"
    )
    repro = attempt.repro
    return "\n".join(
        [
            "## Furnace Guard repair (draft, human review required)",
            "",
            f"**Failure mode:** {attempt.failure_mode_key}",
            "",
            "### 1. Failing test first",
            f"`{test_path}` was written before any fix and calibrated on the base revision.",
            f"- fails on the PR head: **{repro.head_fails if repro else '?'}**",
            f"- passes on the base revision: **{repro.base_passes if repro else '?'}**",
            "",
            "### 2. Fix",
            explanation,
            "",
            "### 3. Validation (sandboxed)",
            "- new regression test: "
            + str(
                attempt.candidates[0].results.get("regression_test") if attempt.candidates else "–"
            ),
            "- existing tests: "
            + str(
                attempt.candidates[0].results.get("existing_tests") if attempt.candidates else "–"
            ),
            "",
            "### 4. Performance (same workload, same endpoint)",
            perf_table,
            "",
            "Furnace never merges. Review the diff, then merge or close.",
        ]
    )
