"""Guard on the second fixture (F2 agent-actions-py): impact analysis, then the selected
suite items executed in the sandbox, for every F2 PR scenario. No GPU item exists in the F2
suite, so this runs without the lab endpoint.

  FURNACE_BENCH_DATE=<date> uv run python bench/f2_guard.py

Expected (the author's intent, fixed with the scenarios): R4 (refund confirmation deleted)
selects and FAILS security:approval_gate; the docs-only and wording PRs do not fail anything.
Output: bench/results/<date>/f2_guard.{json,md}
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from common import ROOT, manifest, md_table, results_dir, write_json

sys.path.insert(0, str(ROOT / "fixtures" / "scenarios"))

from f2_scenarios import SCENARIOS, materialize
from f2_suite import F2_SUITE
from furnace.guardian.execute import (
    GuardContext,
    prepare,
    run_items,
    selected_items,
    verdict,
)
from furnace.guardian.impact import analyze_impact, analyze_tree
from furnace_bench.schema import AdapterName, BenchTarget

UNUSED = BenchTarget(adapter=AdapterName.vllm, base_url="http://localhost:8100/v1", model="lab")
EXPECT_FAIL = {"f2_r4_refund_approval_removed": {"security:approval_gate"}}


def main() -> None:
    rows, out = [], []
    tmp = Path(tempfile.mkdtemp(prefix="f2-guard-"))
    try:
        base_root = materialize(None, tmp / "base")
        base = analyze_tree(base_root)
        for s in SCENARIOS:
            head_root = materialize(s, tmp / s.name)
            imp = analyze_impact(base, analyze_tree(head_root), F2_SUITE)
            items = selected_items(imp, F2_SUITE)
            work, b, h = prepare(base_root, head_root)
            try:
                ctx = GuardContext(
                    base=b, head=h, questions=[], target=UNUSED, max_prompt_tokens=4096
                )
                res = run_items(items, ctx)
            finally:
                shutil.rmtree(work, ignore_errors=True)
            fails = {r.key for r in res if r.verdict == "fail"}
            want = EXPECT_FAIL.get(s.name, set())
            errors = {r.key for r in res if r.verdict in ("error", "skip")}
            ok = fails == want and not errors  # an item that could not run is never "as expected"
            out.append(
                {
                    "scenario": s.name,
                    "description": s.description,
                    "categories": sorted(imp.categories),
                    "selected": [i.key for i in items],
                    "results": [
                        {"key": r.key, "verdict": r.verdict, "detail": r.detail} for r in res
                    ],
                    "conclusion": verdict(res),
                    "expected_failures": sorted(want),
                    "as_expected": ok,
                }
            )
            rows.append(
                [
                    s.name,
                    ", ".join(i.key for i in items),
                    verdict(res),
                    ", ".join(sorted(fails)) or "–",
                    "yes" if ok else "NO",
                ]
            )
            print(rows[-1], flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    d = results_dir()
    write_json(d / "f2_guard.json", {"manifest": manifest(), "scenarios": out})
    text = [
        "# Guard on F2 (agent-actions-py, the second Python fixture)",
        "",
        "Impact analysis, then the selected items executed in the sandbox. F2 is a development "
        "fixture (written by the developer agent from the plan's F2 specification); expected "
        "failures were fixed with the scenarios.",
        "",
        md_table(["scenario", "selected", "conclusion", "failed", "as expected"], rows),
    ]
    (d / "f2_guard.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
