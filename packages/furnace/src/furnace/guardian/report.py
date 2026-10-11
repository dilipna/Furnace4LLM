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


WHY = {
    "fm:prefix_instability": (
        "A per-request value now sits at the head of the system prompt, so no two requests "
        "share a prompt prefix. vLLM's automatic prefix caching reuses KV-cache blocks only "
        "for an identical token prefix, so every request prefills its whole prompt again: "
        "time to first token rises and the prefix-cache hit rate collapses."
    ),
}


def _hit(c: dict[str, Any], i: int) -> str:
    hit = (c.get("prefix_hit_rate") or (None, None))[i]
    return f"{hit * 100:.0f}%" if hit is not None else "–"


def _ci(c: dict[str, Any]) -> str:
    ci = c.get("ci_pct")
    return f"{ci[0]:+.1f}% to {ci[1]:+.1f}%" if ci else "–"


def repair_pr_body(attempt: Any, perf: dict[str, Any], explanation: str, test_path: str) -> str:
    """The nine things a reviewer needs: what changed, why it regressed, the evidence, the
    repair, why earlier candidates failed, which tests passed, what the benchmark shows,
    what remains uncertain, and what exactly needs a human decision."""
    sel = getattr(attempt, "selected", None)
    cands = list(getattr(attempt, "candidates", []) or [])
    chosen = cands[sel] if sel is not None and sel < len(cands) else (cands[-1] if cands else None)
    rejected = []
    for c in cands:
        if c is chosen:
            continue
        cp = c.results.get("perf") or {}
        why = (
            "; ".join(cp.get("reasons") or [])
            or cp.get("summary")
            or (
                f"regression test {c.results.get('regression_test')}, "
                f"existing tests {c.results.get('existing_tests')}"
            )
        )
        rejected.append(f"- `{c.strategy}` rejected: {why}")
    loc = list(getattr(attempt, "localization", []) or [])
    changed = [
        f"- `{lc.file}`"
        + (
            f" lines {lc.hunk.new_start}-{lc.hunk.new_start + max(lc.hunk.new_lines, 1) - 1}"
            if lc.hunk
            else ""
        )
        + ": "
        + "; ".join(lc.reasons)
        for lc in loc[:3]
    ] or ["- (no hunk localized)"]
    hv, cv = perf.get("head_vs_base") or {}, perf.get("candidate_vs_base") or {}
    rows = [
        f"| {name} | {c.get('baseline')} ms | {c.get('value')} ms | {c.get('change_pct'):+} % | "
        f"{_ci(c)} | {_hit(c, 1)} | {str(c.get('verdict', '')).upper()} |"
        for name, c in (("PR head", hv), ("This repair", cv))
        if c
    ]
    perf_table = (
        "\n".join(
            [
                "| revision vs base | base p95 TTFT | p95 TTFT | change | 95% CI | prefix-cache hit | gate |",
                "|---|---:|---:|---:|---|---:|---|",
                *rows,
            ]
        )
        if rows
        else "_No performance run attached._"
    )
    reasons = [f"- {r}" for r in perf.get("reasons") or []]
    runs = hv.get("runs")
    n_req = (
        len((hv.get("samples_ms") or {}).get("value", [[]])[0]) if hv.get("samples_ms") else None
    )
    repro = attempt.repro
    return "\n".join(
        [
            "## Furnace Guard repair (draft, human review required)",
            "",
            f"**Failure mode:** `{attempt.failure_mode_key}` (a supported regression signature)",
            "",
            "### 1. What changed in the pull request",
            *changed,
            "",
            "### 2. Why it is slower",
            WHY.get(attempt.failure_mode_key, "See the failure mode above."),
            "",
            "### 3. Evidence",
            f"- `{test_path}` was written before any fix and calibrated on the base revision; "
            f"fails on the PR head: **{repro.head_fails if repro else '?'}**, passes on the base: "
            f"**{repro.base_passes if repro else '?'}**",
            f"- prefix-cache hit rate: base {_hit(hv, 0)}, PR head {_hit(hv, 1)}"
            if hv
            else "- no benchmark run attached",
            f"- p95 TTFT of the PR head vs base: {hv.get('change_pct'):+}% (95% CI {_ci(hv)})"
            if hv
            else "",
            "",
            "### 4. The repair",
            explanation,
            "",
            "### 5. Candidates rejected before this one",
            *(rejected or ["- none: the first candidate passed"]),
            "",
            "### 6. Tests (sandboxed, no network)",
            "- new regression test: "
            + str(chosen.results.get("regression_test") if chosen else "–"),
            "- existing tests: " + str(chosen.results.get("existing_tests") if chosen else "–"),
            "",
            "### 7. Benchmark (same workload and endpoint, base / PR / repair interleaved)",
            perf_table,
            "",
            "Perf gate decision for this repair:",
            *(reasons or ["- (no perf gate run)"]),
            "",
            "### 8. What remains uncertain",
            f"- {runs or '?'} runs per revision"
            + (f" of {n_req} measured requests each" if n_req else "")
            + "; the interval is a hierarchical bootstrap and is coarse at this size.",
            "- One model and one endpoint (the lab vLLM); the effect on other hardware, models "
            "or traffic mixes was not measured here.",
            "- Functional equivalence is only as strong as the existing tests plus the new "
            "regression test.",
            "",
            "### 9. What needs your decision",
            "- Whether the behavior change described in section 4 is acceptable for this "
            "product (it is the only intended behavior change).",
            "- Merge or close. Furnace never merges and never pushes to your branches.",
        ]
    )
