"""The landing page's PR diff is generated from the R1 scenario; it must never drift from it."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_landing_pr_diff_matches_the_scenario():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_pr_diff.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
