"""Snapshot the API's read-only evidence routes for a recorded-only web deployment.

  uv run python scripts/export_bench_snapshot.py            # writes the files
  uv run python scripts/export_bench_snapshot.py --check    # exit 1 if they are stale

A web deployment without the API (NEXT_PUBLIC_RECORDED_ONLY=true, e.g. Vercel alone) still
shows every recorded result: apps/web/lib/api.ts answers /api/bench/* from
apps/web/lib/bench-snapshot.json, and the Inference Lab reads the recorded telemetry from
apps/web/public/recorded/live-recorded.json. Both are produced here by calling the API's own
route functions on the committed bench/results, so they are exactly what the API would
return; a test fails when a committed result changes and the snapshot was not regenerated.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
OUT = WEB / "lib" / "bench-snapshot.json"
OUT_RECORDED = WEB / "public" / "recorded" / "live-recorded.json"


def build() -> tuple[dict[str, Any], dict[str, Any] | None]:
    from furnace_api.routers import bench, live

    r: dict[str, Any] = {}
    campaigns = bench.list_campaigns()
    r["/api/bench/campaigns"] = campaigns
    for c in campaigns:
        name = c["name"]
        r[f"/api/bench/campaigns/{name}"] = bench.get_campaign(name)
        for rq in c["available"]:
            r[f"/api/bench/campaigns/{name}/{rq}"] = bench.get_rq(name, rq)
        rq3 = bench.bench_dir() / "results" / name / "rq3"
        for p in sorted(rq3.glob("*.targeted.check.md")) if rq3.is_dir() else []:
            sc = p.name.removesuffix(".targeted.check.md")
            r[f"/api/bench/campaigns/{name}/rq3/{sc}/check"] = bench.get_rq3_check(name, sc)
    for path, fn in (
        ("/api/bench/workload", bench.get_workload),
        ("/api/bench/guard-live", bench.get_guard_live),
    ):
        with contextlib.suppress(HTTPException):  # the API answers 404 here too
            r[path] = fn()
    try:
        recorded = live.recorded()
    except HTTPException:
        recorded = None
    return {"source": "scripts/export_bench_snapshot.py", "responses": r}, recorded


def _text(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    snap, recorded = build()
    want = {OUT: _text(snap)}
    if recorded is not None:
        want[OUT_RECORDED] = _text(recorded)
    if a.check:
        stale = [
            f for f, t in want.items() if not f.is_file() or f.read_text(encoding="utf-8") != t
        ]
        for f in stale:
            print(f"stale: {f.relative_to(ROOT)} (run scripts/export_bench_snapshot.py)")
        if not stale:
            print("up to date")
        return 1 if stale else 0
    for f, t in want.items():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(t, encoding="utf-8", newline="\n")
        print(f"wrote {f.relative_to(ROOT)} ({len(t.encode()) / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
