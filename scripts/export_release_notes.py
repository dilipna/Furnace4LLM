"""Snapshot actual public GitHub release notes for the next unpublished site build."""

import json
import os
import urllib.request
from pathlib import Path

url = "https://api.github.com/repos/dilipna/Furnace4LLM/releases"
headers = {"Accept": "application/vnd.github+json", "User-Agent": "Furnace-release-preview"}
if os.environ.get("GH_TOKEN"):
    headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
request = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- fixed official repository API
    releases = json.load(response)
notes = [
    {key: release[key] for key in ("tag_name", "name", "published_at", "html_url", "body")}
    for release in releases
    if not release["draft"] and release["published_at"]
]
root = Path(__file__).resolve().parents[1] / "apps/web/public/downloads"
root.mkdir(parents=True, exist_ok=True)
(root / "releases.json").write_text(
    json.dumps({"source": url, "releases": notes}, indent=2) + "\n", encoding="utf-8"
)
print(f"Recorded {len(notes)} public releases; no draft release published")
