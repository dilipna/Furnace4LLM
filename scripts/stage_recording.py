"""Stage an executed recording for local review only. Never upload or synthesize media."""

import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1])
record = json.loads((source / "record.json").read_text(encoding="utf-8"))
assert record["result"] == "passed" and record["quit_and_lease_released"]
assert record["ask"]["output"] and record["interrupted"]["status"] == "interrupted"
repro = record["restart"]["reproducibility"]
assert repro["compared"] > 0 and repro["reference_launch_id"] != repro["current_launch_id"]
target = root / "apps/web/public/product/generated"
target.mkdir(parents=True, exist_ok=True)
for name in ("prepared", "ask", "evaluated", "crashed", "reproducibility"):
    shutil.copy2(source / (name + ".png"), target / (name + ".png"))
video = source / "studio-journey.webm"
shutil.copy2(video, target / video.name)


def stamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    return f"{millis // 3600000:02}:{millis // 60000 % 60:02}:{millis // 1000 % 60:02}.{millis % 1000:03}"


events = record["events"]
captions = ["WEBVTT", ""]
for index, event in enumerate(events):
    end = events[index + 1]["seconds"] if index + 1 < len(events) else event["seconds"] + 3
    captions += [f"{stamp(event['seconds'])} --> {stamp(end)}", event["caption"], ""]
(target / "captions.vtt").write_text("\n".join(captions), encoding="utf-8")
# Local evidence omits the temporary workspace path; no session token is present.
record.pop("workspace", None)
(target / "record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
results = record["baseline"]["results"]
manifest = {
    "source_commit": record["build"]["commit"],
    "video": video.name,
    "bytes": video.stat().st_size,
    "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
    "rule_passed": sum(r["status"] == "check_pass" for r in results),
    "rule_total": len(results),
    "compared": repro["compared"],
    "identical": repro["identical"],
    "published": False,
}
manifest["image_sizes"] = {
    name: list(struct.unpack(">II", (target / (name + ".png")).read_bytes()[16:24]))
    for name in ("prepared", "ask", "evaluated", "crashed", "reproducibility")
}
(target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Staged actual recording locally; no media published", manifest["sha256"])
