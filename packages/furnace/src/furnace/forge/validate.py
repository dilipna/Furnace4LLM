"""Validate a Forge change set before it is offered as a pull request.

1. Behavior preservation: prompts rendered through the harness are byte-identical
   before and after the change set (evalability refactors must not change behavior).
2. The installed tests and the repository's existing tests pass in the sandbox.
3. Re-scan of the forged repository: which Blueprint findings the change set resolved.
"""

from __future__ import annotations

import difflib
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from furnace.blueprint.rules import run_rules
from furnace.forge.harness import HARNESS_FILE
from furnace.forge.planner import ForgeResult, apply
from furnace.guardian.repair.regression import render_in_sandbox
from furnace.reconstruction.build import reconstruct
from furnace.sandbox.docker_sandbox import pytest_in_sandbox


@dataclass
class ForgeValidation:
    prompts_identical: bool
    installed_tests: str  # pass | fail | none
    existing_tests: str
    resolved_findings: list[str] = field(default_factory=list)
    remaining_findings: list[str] = field(default_factory=list)
    logs: dict[str, str] = field(default_factory=dict)
    patch: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.prompts_identical
            and self.installed_tests in ("pass", "none")
            and self.existing_tests in ("pass", "none")
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "prompts_identical": self.prompts_identical,
            "installed_tests": self.installed_tests,
            "existing_tests": self.existing_tests,
            "resolved_findings": self.resolved_findings,
            "remaining_findings": self.remaining_findings,
        }


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-20:])


def unified_patch(original: Path, result: ForgeResult) -> str:
    out: list[str] = []
    for path in sorted(result.files):
        before = (
            (original / path).read_text(encoding="utf-8").splitlines(keepends=True)
            if (original / path).exists()
            else []
        )
        after = result.files[path].splitlines(keepends=True)
        out.extend(
            difflib.unified_diff(
                before, after, fromfile=f"a/{path}" if before else "/dev/null", tofile=f"b/{path}"
            )
        )
    return "".join(out)


def validate(repo: Path, result: ForgeResult, questions: list[str]) -> ForgeValidation:
    work = Path(tempfile.mkdtemp(prefix="furnace-forge-"))
    try:
        ign = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "traces")
        orig = Path(shutil.copytree(repo, work / "original", ignore=ign))
        forged = Path(shutil.copytree(repo, work / "forged", ignore=ign))
        apply(result, forged)
        harness = result.files.get(HARNESS_FILE)
        if harness and not (orig / HARNESS_FILE).exists():
            (orig / HARNESS_FILE).write_text(harness, encoding="utf-8")

        identical = True
        logs: dict[str, str] = {}
        if (orig / HARNESS_FILE).exists():
            before = render_in_sandbox(orig, questions[:3])
            after = render_in_sandbox(forged, questions[:3])
            identical = before == after
            if not identical:
                logs["render_diff"] = "rendered messages differ after the change set"

        has_installed = any(
            p.startswith("tests/furnace/") and p.endswith(".py") for p in result.files
        )
        installed = pytest_in_sandbox(forged, "tests/furnace") if has_installed else None
        existing_dir = (forged / "tests").exists() and any((forged / "tests").glob("test_*.py"))
        existing = (
            pytest_in_sandbox(forged, "tests", "--ignore=tests/furnace") if existing_dir else None
        )
        if installed:
            logs["installed_tests"] = _tail(installed.stdout + installed.stderr)
        if existing:
            logs["existing_tests"] = _tail(existing.stdout + existing.stderr)

        before_rules = {r.rule_id for r in run_rules(reconstruct(orig))}
        after_rules = {r.rule_id for r in run_rules(reconstruct(forged))}
        return ForgeValidation(
            prompts_identical=identical,
            installed_tests="none" if installed is None else ("pass" if installed.ok else "fail"),
            existing_tests="none" if existing is None else ("pass" if existing.ok else "fail"),
            resolved_findings=sorted(before_rules - after_rules),
            remaining_findings=sorted(after_rules),
            logs=logs,
            patch=unified_patch(repo, result),
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
