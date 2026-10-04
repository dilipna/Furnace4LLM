"""Failure -> failing test -> localization -> candidate -> sandbox validation -> patch.

The order is enforced: no candidate is generated unless the regression test was
written first and shown to FAIL on the PR head and PASS on the base revision.
Repairs are proposed as patches / draft PRs; nothing is merged or deployed.
"""

from __future__ import annotations

import difflib
import hashlib
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from furnace.contracts.guard import (
    LocalizationCandidate,
    RegressionTest,
    RepairAttempt,
    RepairCandidate,
    RepairStatus,
    Repro,
)
from furnace.forge.harness import HARNESS_FILE, write_harness
from furnace.guardian.impact import ImpactResult
from furnace.guardian.repair.regression import (
    min_shared_prefix,
    prefix_stability_test,
    render_in_sandbox,
)
from furnace.guardian.repair.strategies import StrategyError, move_dynamic_to_suffix
from furnace.reconstruction.build import reconstruct
from furnace.sandbox.docker_sandbox import SandboxResult, pytest_in_sandbox

Progress = Callable[[str, str], None]


@dataclass
class RepairOutcome:
    attempt: RepairAttempt
    patch: str = ""  # unified diff against the PR head (includes the regression test)
    test_path: str = ""
    logs: dict[str, str] = field(default_factory=dict)
    perf: dict[str, Any] = field(default_factory=dict)


def _copy(src: Path, dest: Path) -> Path:
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "traces"),
    )
    return dest


def _unified(root_a: Path, root_b: Path, paths: list[str]) -> str:
    out: list[str] = []
    for p in sorted(set(paths)):
        a = (
            (root_a / p).read_text(encoding="utf-8").splitlines(keepends=True)
            if (root_a / p).exists()
            else []
        )
        b = (
            (root_b / p).read_text(encoding="utf-8").splitlines(keepends=True)
            if (root_b / p).exists()
            else []
        )
        out.extend(difflib.unified_diff(a, b, fromfile=f"a/{p}", tofile=f"b/{p}"))
    return "".join(out)


def _tail(r: SandboxResult) -> str:
    text = (r.stdout + "\n" + r.stderr).strip()
    return "\n".join(text.splitlines()[-25:])


def repair_prefix_instability(
    base_root: Path,
    head_root: Path,
    impact: ImpactResult,
    *,
    questions: list[str],
    change_label: str,
    progress: Progress | None = None,
    perf_check: Callable[[Path, Path, Path], dict[str, Any]] | None = None,
) -> RepairOutcome:
    say = progress or (lambda stage, msg: None)
    attempt = RepairAttempt(trigger={"pr": change_label}, failure_mode_key="fm:prefix_instability")
    outcome = RepairOutcome(attempt=attempt)

    touched = {t.node_key: t for t in impact.impact.touched}
    sysmsg = next(
        (
            t
            for k, t in touched.items()
            if k.endswith("#system") and t.attr_changes.get("dynamic_head") == (False, True)
        ),
        None,
    )
    if sysmsg is None:
        attempt.status = RepairStatus.rejected
        outcome.logs["diagnosis"] = "no system message changed from prefix-stable to dynamic-head"
        return outcome

    work = Path(tempfile.mkdtemp(prefix="furnace-repair-"))
    base = _copy(base_root, work / "base")
    head = _copy(head_root, work / "head")

    # 1. harness (generated from each revision's own handler)
    attempt.status = RepairStatus.reproducing
    write_harness(reconstruct(base))
    write_harness(reconstruct(head))
    say("harness", f"generated {HARNESS_FILE} from the route handler")

    # 2. regression test FIRST, calibrated on the base revision
    base_shared = min_shared_prefix(render_in_sandbox(base, questions))
    head_shared = min_shared_prefix(render_in_sandbox(head, questions))
    test_path, test_src = prefix_stability_test(
        questions=questions,
        base_shared=base_shared,
        failure_mode="prefix instability (dynamic value at the head of the system prompt)",
        change=change_label,
    )
    for root in (base, head):
        (root / test_path).parent.mkdir(parents=True, exist_ok=True)
        (root / test_path).write_text(test_src, encoding="utf-8")
    attempt.regression_test = RegressionTest(
        path=test_path,
        kind="pytest_deterministic",
        content_hash=hashlib.sha256(test_src.encode()).hexdigest(),
    )
    outcome.test_path = test_path
    say(
        "regression_test",
        f"wrote {test_path}: base shares {base_shared} chars, PR head shares {head_shared}",
    )

    # 3. reproduce: must FAIL on head and PASS on base, otherwise stop
    on_head = pytest_in_sandbox(head, test_path)
    on_base = pytest_in_sandbox(base, test_path)
    attempt.repro = Repro(head_fails=not on_head.ok, base_passes=on_base.ok, logs=_tail(on_head))
    outcome.logs["repro_head"], outcome.logs["repro_base"] = _tail(on_head), _tail(on_base)
    if not (attempt.repro.head_fails and attempt.repro.base_passes):
        attempt.status = RepairStatus.repro_failed
        say(
            "reproduce",
            f"could not reproduce (head fails={attempt.repro.head_fails}, base passes={attempt.repro.base_passes}); no repair attempted",
        )
        return outcome
    attempt.status = RepairStatus.reproduced
    say("reproduce", "regression test fails on the PR head and passes on the base revision")

    # 4. localize: hunks that touch the system message construction
    attempt.status = RepairStatus.localizing
    sys_path, fn_part = sysmsg.node_key.removeprefix("prompt:").split("::", 1)
    function = fn_part.removesuffix("#system")
    for cf in impact.impact.changed:
        if cf.path != sys_path:
            continue
        for h in cf.hunks:
            attempt.localization.append(
                LocalizationCandidate(
                    node_key=sysmsg.node_key,
                    file=cf.path,
                    hunk=h,
                    score=1.0 if h.new_lines > 1 else 0.6,
                    reasons=[
                        "hunk lies in the system-message construction whose dynamic_head changed False -> True",
                        f"static prefix shrank from {sysmsg.attr_changes.get('static_prefix_chars', ('?', '?'))[0]} to {sysmsg.attr_changes.get('static_prefix_chars', ('?', '?'))[1]} chars",
                    ],
                )
            )
    attempt.localization.sort(key=lambda c: -c.score)
    say("localize", f"{len(attempt.localization)} hunk(s) in {sys_path}::{function}")

    # 5. candidate repair (deterministic rule strategy)
    attempt.status = RepairStatus.generating
    cand = _copy(head, work / "candidate")
    try:
        edit = move_dynamic_to_suffix(
            sys_path, (head / sys_path).read_text(encoding="utf-8"), function
        )
    except StrategyError as exc:
        attempt.status = RepairStatus.rejected
        outcome.logs["strategy"] = str(exc)
        say("generate", f"rule strategy not applicable: {exc}")
        return outcome
    (cand / sys_path).write_text(edit.after, encoding="utf-8")
    # Diff against the *original* PR head: the repair PR adds the regression test (and the
    # harness it imports, if the repository does not have one yet) together with the fix.
    diff = _unified(head_root, cand, [sys_path, test_path, HARNESS_FILE])
    candidate = RepairCandidate(
        strategy="rule:prefix_stability.move_dynamic_to_suffix",
        diff=diff,
        results={"explanation": edit.explanation},
    )
    attempt.candidates.append(candidate)
    say("generate", edit.explanation)

    # 6. validate in the sandbox: new regression test + existing tests
    attempt.status = RepairStatus.validating
    new_test = pytest_in_sandbox(cand, test_path)
    all_tests = pytest_in_sandbox(cand, "tests")
    candidate.results.update(
        regression_test="pass" if new_test.ok else "fail",
        existing_tests="pass" if all_tests.ok else "fail",
        regression_test_log=_tail(new_test),
        existing_tests_log=_tail(all_tests),
    )
    say(
        "validate",
        f"regression test {candidate.results['regression_test']}, existing tests {candidate.results['existing_tests']}",
    )
    if perf_check is not None and new_test.ok and all_tests.ok:
        outcome.perf = perf_check(base, head, cand)
        candidate.results["perf"] = outcome.perf
        say("benchmark", str(outcome.perf.get("summary", "")))
    passed = (
        new_test.ok
        and all_tests.ok
        and (perf_check is None or bool(outcome.perf.get("within_budget")))
    )
    candidate.verdict = "pass" if passed else "fail"
    attempt.selected = 0 if passed else None
    attempt.status = RepairStatus.verified if passed else RepairStatus.rejected
    outcome.patch = diff if passed else ""
    shutil.rmtree(work, ignore_errors=True)
    return outcome
