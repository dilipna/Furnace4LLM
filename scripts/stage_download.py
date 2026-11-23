"""Stage verified local bytes, or link an already approved public release. Never publish."""

import argparse
import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_asset(metadata: dict, release: dict, tag: str) -> dict:
    if release.get("draft") is not False or not release.get("published_at"):
        raise ValueError("Release is not public; owner publication approval is still required")
    expected = (
        "https://github.com/dilipna/Furnace4LLM/releases/download/"
        + urllib.parse.quote(tag, safe="")
        + "/"
        + metadata["file"]
    )
    for asset in release.get("assets", []):
        if asset.get("name") == metadata["file"]:
            if (
                asset.get("size") != metadata["bytes"]
                or asset.get("digest") != "sha256:" + metadata["sha256"]
            ):
                raise ValueError("Published bytes differ from the reviewed candidate")
            if urllib.parse.unquote(asset.get("browser_download_url", "")) != urllib.parse.unquote(
                expected
            ):
                raise ValueError("Unexpected download origin or asset URL")
            return {
                **metadata,
                "download_url": expected,
                "published": True,
                "published_at": release["published_at"],
            }
    raise ValueError("Installer is missing from the public release")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--published-tag", help="Read an ALREADY published release; does not create one"
    )
    args = parser.parse_args()
    source = ROOT / "dist/windows"
    metadata = json.loads((source / "installer.json").read_text())
    name = metadata["file"]
    assert Path(name).name == name and name.endswith(".exe")
    binary = source / name
    assert binary.stat().st_size == metadata["bytes"]
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == metadata["sha256"]
    if args.published_tag:
        url = (
            "https://api.github.com/repos/dilipna/Furnace4LLM/releases/tags/"
            + urllib.parse.quote(args.published_tag, safe="")
        )
        headers = {"User-Agent": "Furnace-release-preview"}
        if os.environ.get("GH_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=30
        ) as response:
            metadata = release_asset(metadata, json.load(response), args.published_tag)
    target = ROOT / "apps/web/public/downloads"
    target.mkdir(parents=True, exist_ok=True)
    assert target.resolve().is_relative_to(ROOT.resolve())
    # Only generated copies are removed; originals remain in dist/windows.
    for previous in target.glob("Furnace-*-windows-x64.exe"):
        previous.unlink()
    if not args.published_tag:
        shutil.copy2(binary, target / name)
    (target / "installer.json").write_text(json.dumps(metadata, indent=2) + "\n")
    shutil.copy2(source / "SHA256SUMS", target / "SHA256SUMS")
    print(
        "Staged",
        "public release link" if args.published_tag else "unpublished local installer",
        name,
    )


if __name__ == "__main__":
    main()
