"""Prepare the GitHub demo repository from fixture F1.

  uv run python scripts/demo_repo.py init  DIR               # copy F1 (no runtime dirs) into DIR
  uv run python scripts/demo_repo.py apply DIR r1_dynamic_head  # apply a scripted PR scenario in place

The scenario edits are exactly the ones FurnaceBench uses (fixtures/scenarios/f1_scenarios.py),
so the live demo PR is the same change that was benchmarked.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"))

from f1_scenarios import F1, SCENARIOS, by_name

IGNORE = shutil.ignore_patterns(
    ".venv", "traces", "__pycache__", ".pytest_cache", "furnace_harness.py", "ground_truth.yaml"
)


def init(dest: Path) -> None:
    if dest.exists() and any(p.name != ".git" for p in dest.iterdir()):
        raise SystemExit(f"{dest} is not empty (a .git directory alone is fine)")
    shutil.copytree(F1, dest, ignore=IGNORE, dirs_exist_ok=True)
    print(f"copied F1 into {dest}")


def apply(dest: Path, name: str) -> None:
    names = {s.name for s in SCENARIOS}
    if name not in names:
        raise SystemExit(f"unknown scenario {name}; choose one of: {', '.join(sorted(names))}")
    sc = by_name(name)
    for path, old, new in sc.edits:
        p = dest / path
        raw = p.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        if old not in text:
            raise SystemExit(f"{path}: expected text not found (is {dest} a clean F1 copy?)")
        text = text.replace(old, new, 1)
        # Keep the file's own line endings so the PR diff shows only the scenario's change.
        p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"applied {name}: {sc.description}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "init":
        init(Path(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == "apply":
        apply(Path(sys.argv[2]), sys.argv[3])
    else:
        raise SystemExit(__doc__)
