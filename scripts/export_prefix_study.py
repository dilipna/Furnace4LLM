"""Export verified prefix-study observations for the website; --check refuses stale data."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "experiments/prefix-cache"
DEST = ROOT / "apps/web/lib/prefix-study.json"


def snapshot() -> dict:
    spec = importlib.util.spec_from_file_location("prefix_review", STUDY / "review.py")
    assert spec and spec.loader
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    checked = review.audit(review.DEFAULT_CAMPAIGN)
    data, manifest = checked["data"], checked["manifest"]
    return {
        "campaign": manifest["campaign"],
        "measuredDate": manifest["started_utc"][:10],
        "model": manifest["model"],
        "modelRevision": manifest["model_revision"],
        "image": manifest["image"],
        "gpu": "RTX 3050 Ti Laptop · 4 GB",
        "measuredRequests": checked["checks"]["verified_measured_requests"],
        "successfulRuns": checked["checks"]["verified_runs"],
        "startupFailures": sum(r["status"] != "success" for r in manifest["attempts"]),
        "warmups": manifest["warmup"] * checked["checks"]["verified_runs"],
        "reductionPercent": 100 * (1 - data["D"]["p50"] / data["C"]["p50"]),
        "conditions": [
            {
                "id": key,
                "label": checked["labels"][key],
                "p50": value["p50"],
                "p95": value["p95"],
                "tokensPerSecond": value["tok_s"],
                "cacheRate": value["cache_rate"],
                "runs": [
                    {"repeat": r["repeat"], "p50": r["ttft_p50_ms"], "p95": r["ttft_p95_ms"]}
                    for r in value["runs"]
                ],
            }
            for key, value in data.items()
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(snapshot(), indent=2) + "\n"
    if args.check:
        if not DEST.is_file() or DEST.read_text(encoding="utf-8") != text:
            print("Website prefix-study snapshot is stale; run scripts/export_prefix_study.py")
            return 1
        print("Website snapshot matches independently verified measurements.")
    else:
        DEST.write_text(text, encoding="utf-8")
        print("Wrote apps/web/lib/prefix-study.json from verified observations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
