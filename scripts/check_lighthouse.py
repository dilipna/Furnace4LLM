"""Report the measured scores; fail rather than relax the owner's >=90 rule."""

import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if report.get("runtimeError"):
    raise SystemExit(str(report["runtimeError"]))
scores = {
    key: round(report["categories"][key]["score"] * 100)
    for key in ("performance", "accessibility", "seo")
}
print(
    json.dumps(
        {
            "lighthouse_version": report["lighthouseVersion"],
            "fetch_time": report["fetchTime"],
            "scores": scores,
        },
        indent=2,
    )
)
if any(score < 90 for score in scores.values()):
    raise SystemExit(
        "Lighthouse acceptance requires >=90 in each category; inspect the retained report."
    )
