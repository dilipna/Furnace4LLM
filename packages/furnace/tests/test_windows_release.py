import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "windows_release_test", Path(__file__).resolve().parents[3] / "scripts/package_release.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def installer(tmp_path):
    binary = tmp_path / "Furnace-0.1.0-test-windows-x64.exe"
    binary.write_bytes(b"authored test installer")
    info = {
        "file": binary.name,
        "version": "0.1.0",
        "commit": "current",
        "source_dirty": False,
        "bytes": binary.stat().st_size,
        "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
    path = tmp_path / "installer.json"
    path.write_text(json.dumps(info))
    return path, binary, info


def test_windows_artifact_inventory_matches_real_bytes(installer):
    path, binary, _ = installer
    assert module.validate_windows(path, "current", "0.1.0")[0] == binary
    binary.write_bytes(b"changed")
    with pytest.raises(SystemExit, match="integrity"):
        module.validate_windows(path, "current", "0.1.0")


@pytest.mark.parametrize(
    "patch",
    [
        {"commit": "old"},
        {"version": "9.0"},
        {"source_dirty": True},
        {"file": "../outside-windows-x64.exe"},
        {"sha256": "invalid"},
    ],
)
def test_stale_or_unsafe_windows_input_is_refused(installer, patch):
    path, _, info = installer
    path.write_text(json.dumps({**info, **patch}))
    with pytest.raises(SystemExit):
        module.validate_windows(path, "current", "0.1.0")
