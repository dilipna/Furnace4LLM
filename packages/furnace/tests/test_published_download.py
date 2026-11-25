import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "staging_test", Path(__file__).resolve().parents[3] / "scripts/stage_download.py"
)
assert spec and spec.loader
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def test_only_matching_public_release_assets_can_replace_local_downloads():
    info = {"file": "Furnace-0.1.0-abcdef-windows-x64.exe", "bytes": 123, "sha256": "a" * 64}
    asset = {
        "name": info["file"],
        "size": 123,
        "digest": "sha256:" + info["sha256"],
        "browser_download_url": "https://github.com/dilipna/Furnace4LLM/releases/download/v0.1.0/"
        + info["file"],
    }
    release = {"draft": False, "published_at": "2026-11-23T00:00:00Z", "assets": [asset]}
    result = stage.release_asset(info, release, "v0.1.0")
    assert result["published"] is True and result["download_url"] == asset["browser_download_url"]
    for patch in (
        {"draft": True},
        {"assets": []},
        {"published_at": None},
        {"assets": [{**asset, "size": 124}]},
        {"assets": [{**asset, "digest": "sha256:other"}]},
        {"assets": [{**asset, "browser_download_url": "https://evil.test/file.exe"}]},
    ):
        with pytest.raises(ValueError):
            stage.release_asset(info, {**release, **patch}, "v0.1.0")
