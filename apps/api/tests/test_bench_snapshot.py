"""The recorded-only web build reads a snapshot of the evidence routes; it must match bench/results."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_bench_snapshot_matches_the_committed_results():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_bench_snapshot.py"), "--check"],
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "FURNACE_BENCH_DIR"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
