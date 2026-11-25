"""Stage actual installed-model footage locally; never publish."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1])
record = json.loads((source / "record.json").read_text(encoding="utf-8"))
assert (
    record["kind"] == "private-document-recording"
    and record["result"] == "passed"
    and record["quit_and_lease_released"]
)
assert record["answer"]["receipt"]["status"] == "checked"
assert record["installed_build"]["experience"] == "private-documents-preview"
target = root / "apps/web/public/product/generated/everyday"
target.mkdir(parents=True, exist_ok=True)
for name in (
    "journey.webm",
    "home.png",
    "document.png",
    "answer.png",
    "receipt.png",
    "record.json",
):
    shutil.copy2(source / name, target / name)


def stamp(t):
    ms = round(t * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"


events = record["events"]
captions = ["WEBVTT", ""]
for index, event in enumerate(events):
    end = events[index + 1]["seconds"] if index + 1 < len(events) else event["seconds"] + 2
    captions += [stamp(event["seconds"]) + " --> " + stamp(end), event["caption"], ""]
(target / "captions.vtt").write_text("\n".join(captions), encoding="utf-8")
manifest = {
    "kind": record["kind"],
    "source_commit": record["installed_build"]["commit"],
    "model": record["model"],
    "accelerator": record["accelerator"],
    "files": {},
}
for item in target.iterdir():
    if item.name == "manifest.json":
        continue
    manifest["files"][item.name] = {
        "bytes": item.stat().st_size,
        "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
    }
(target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("Staged executed footage locally; nothing published")
