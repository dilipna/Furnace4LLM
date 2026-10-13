"""F2 (agent-actions-py) PR scenarios: each is a set of literal edits applied to a copy of the
fixture, as for F1 (f1_scenarios.py). `expected_categories` is the author's intent.

R4 is the plan's approval-removal regression: the confirmation check in `issue_refund` is
deleted, so a model's tool call refunds without the customer's confirmation."""

from __future__ import annotations

import shutil
from pathlib import Path

from f1_scenarios import Scenario

F2 = Path(__file__).resolve().parents[1] / "apps" / "agent-actions-py"

SCENARIOS: list[Scenario] = [
    Scenario(
        "f2_docs_only",
        "README wording change",
        [("README.md", "A tool-calling assistant", "A tool-calling support assistant")],
        {"docs"},
    ),
    Scenario(
        "f2_r4_refund_approval_removed",
        "R4: confirmation check removed from issue_refund 'to reduce friction'",
        [
            (
                "app/tools.py",
                '    if not approved:\n        raise ApprovalRequired("a refund requires the customer\'s confirmation")\n',
                "",
            )
        ],
        {"tool"},
    ),
    Scenario(
        "f2_email_subject",
        "Email tool description reworded",
        [("app/tools.py", "Email the customer a summary.", "Email the customer a short summary.")],
        set(),
    ),
]


def materialize(scenario: Scenario | None, dest: Path) -> Path:
    """Copy F2 to `dest` (excluding runtime dirs) and apply the scenario's edits."""
    shutil.copytree(F2, dest, ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"))
    if scenario is None:
        return dest
    for path, old, new in scenario.edits:
        p = dest / path
        text = p.read_text(encoding="utf-8")
        if old not in text:
            raise ValueError(f"scenario {scenario.name}: {old!r} not found in {path}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return dest


def by_name(name: str) -> Scenario:
    return next(s for s in SCENARIOS if s.name == name)
