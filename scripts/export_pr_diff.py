"""Write the exact diff of an F1 PR scenario for the landing page (apps/web/lib/r1-pr-diff.json).

  uv run python scripts/export_pr_diff.py            # writes the file
  uv run python scripts/export_pr_diff.py --check    # exit 1 if the file is stale

The landing page shows the R1 pull request's change. It must be the change FurnaceBench
measured, not a reconstruction, so it is generated from the scenario's own edits
(fixtures/scenarios/f1_scenarios.py) and a test fails if the two drift apart.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fixtures" / "scenarios"))

from f1_scenarios import F1, by_name  # noqa: E402

OUT = ROOT / "apps" / "web" / "lib" / "r1-pr-diff.json"


def build(name: str = "r1_dynamic_head") -> dict:
    sc = by_name(name)
    files: dict[str, tuple[str, str]] = {}
    for path, old, new in sc.edits:
        before = files[path][1] if path in files else (F1 / path).read_text(encoding="utf-8")
        if old not in before:
            raise ValueError(f"{name}: {old!r} not found in {path}")
        files.setdefault(path, (before, before))
        files[path] = (files[path][0], files[path][1].replace(old, new, 1))
    out = []
    for path, (a, b) in files.items():
        lines = list(
            difflib.unified_diff(
                a.splitlines(), b.splitlines(), f"a/{path}", f"b/{path}", n=1, lineterm=""
            )
        )
        out.append({"path": path, "lines": lines[2:]})  # drop the ---/+++ headers
    return {
        "scenario": name,
        "title": sc.description,
        "source": "fixtures/scenarios/f1_scenarios.py",
        "files": out,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    text = json.dumps(build(), indent=2) + "\n"
    if a.check:
        ok = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        print("up to date" if ok else f"stale: run scripts/export_pr_diff.py to rewrite {OUT}")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
