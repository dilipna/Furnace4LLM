"""Readable saved evidence, with no execution, raw text or inferred quality verdict."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

STATUSES = (
    "framework_pass",
    "framework_fail",
    "exact_pass",
    "exact_fail",
    "check_pass",
    "check_fail",
    "unscored",
    "incomplete",
    "error",
    "not_run",
)


def identifier(value: Any) -> str:
    # Only generated identifiers enter Markdown; never render arbitrary saved text.
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value)
        else "not_recorded"
    )


def evidence_summary(project: dict[str, Any]) -> str:
    endpoint = project["model_endpoint"]
    lines = [
        "# Furnace saved evidence",
        "",
        f"Project ID: `{identifier(project['id'])}`",
        "",
        "This export is a saved snapshot, not a live health check. Opening it runs nothing.",
    ]
    for title, run, digest, current in (
        (
            "Infrastructure fixture (not an LLM)",
            project.get("evaluation"),
            project["configuration_sha256"],
            project["evaluation_verification"] == "current_framework_evidence",
        ),
        (
            "Local-server endpoint observations",
            endpoint.get("evaluation"),
            endpoint["configuration_sha256"],
            endpoint["verification"] == "current_endpoint_observation",
        ),
    ):
        lines.extend(
            ["", f"## {title}", "", f"Current configuration SHA-256: `{identifier(digest)}`"]
        )
        if not run:
            lines.extend(["", "No saved attempt. No execution or passing result is established."])
            continue
        current = (
            current
            and run.get("project_id") == project["id"]
            and run.get("configuration_sha256") == digest
        )
        status = run.get("status")
        status = (
            status if status in {"running", "completed", "interrupted", "failed"} else "unknown"
        )
        lines.extend(
            [
                "",
                f"Saved attempt: **{status}**. Completion alone does not mean its checks passed.",
                f"Run ID: `{identifier(run.get('run_id'))}`",
                f"Recorded configuration SHA-256: `{identifier(run.get('configuration_sha256'))}`",
                "Binding: matches this project/configuration."
                if current
                else "Binding: **unbound or stale; does not verify this configuration**.",
            ]
        )
        results = run.get("results") or []
        counts = Counter(r.get("status") for r in results)
        total = run.get("case_count")
        if type(total) is not int or total < 0:
            total = len(project["cases"]) if current else None
        missing = max(0, total - len(results)) if total is not None else "not recorded"
        lines.extend(
            [
                "",
                f"Recorded result rows: {len(results)}. Missing result rows: {missing}.",
                "Missing rows and unscored cases are not passes.",
                "",
                "| Outcome | Recorded rows |",
                "| --- | --- |",
                *(f"| {name} | {counts[name]} |" for name in STATUSES),
            ]
        )
        unknown = sum(count for name, count in counts.items() if name not in STATUSES)
        if unknown:
            lines.append(f"| unrecognized status | {unknown} |")
    lines.extend(
        [
            "",
            "## How to interpret this evidence",
            "",
            "- Fixture checks exercise deterministic infrastructure, not a model.",
            "- Endpoint observations are HTTP evidence. A declared model/revision is not independently attested.",
            "- Rule checks and output agreement do not establish semantic quality or architecture support.",
            "- Durations are round trips with runtime overhead, not model TTFT or a measured speedup.",
            "- No model baseline or performance comparison is supplied by this summary.",
            "- Prompts, outputs and case text are omitted here; saved case text remains in the kit's JSON files.",
            "- Read workspace-plan.json for exact provenance, retained endpoint history and runtime snapshots.",
        ]
    )
    return "\n".join(lines) + "\n"
