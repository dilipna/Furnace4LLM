"""Read-only gate before an approved Pages deploy: never upload a >25 MiB binary."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "apps/web/out"
metadata = json.loads((root / "downloads/installer.json").read_text())
if not metadata.get("published") or not metadata.get("download_url", "").startswith(
    "https://github.com/dilipna/Furnace4LLM/releases/download/"
):
    raise SystemExit(
        "This is a local preview. Stage the approved public release link before a Pages deploy."
    )
oversized = [
    str(p.relative_to(root))
    for p in root.rglob("*")
    if p.is_file() and p.stat().st_size > 25 * 1024 * 1024
]
if oversized:
    raise SystemExit("Pages file-size limit exceeded: " + ", ".join(oversized))
print("Public-link bundle fits Pages limits. No deploy performed.")
