"""Release labels must describe the bytes that are actually packaged."""

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "scripts/package_release.py"
spec = importlib.util.spec_from_file_location("release_package_under_test", SOURCE)
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def bundle(tmp_path, *, commit="current", dirty=False, payload=b"wheel contents"):
    wheel = tmp_path / "furnace-0.1.0-py3-none-any.whl"
    wheel.write_bytes(payload)
    archive = tmp_path / "preview.zip"
    manifest = {
        "source_commit": commit,
        "source_dirty": dirty,
        "package_version": "0.1.0",
        "wheel_sha256": {wheel.name: hashlib.sha256(payload).hexdigest()},
    }
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("wheels/" + wheel.name, payload)
    return archive, wheel


def test_matching_bundle_and_wheels_are_accepted(tmp_path):
    archive, wheel = bundle(tmp_path)
    release.validate_bundle(archive, [wheel], "current", False, "0.1.0")


@pytest.mark.parametrize(
    "commit,dirty,version",
    [("other", False, "0.1.0"), ("current", True, "0.1.0"), ("current", False, "0.2.0")],
)
def test_different_source_dirty_state_or_version_is_refused(tmp_path, commit, dirty, version):
    archive, wheel = bundle(tmp_path)
    with pytest.raises(SystemExit, match="source/version"):
        release.validate_bundle(archive, [wheel], commit, dirty, version)


def test_changed_external_or_embedded_wheel_is_refused(tmp_path):
    archive, wheel = bundle(tmp_path)
    wheel.write_bytes(b"changed after building")
    with pytest.raises(SystemExit, match="integrity"):
        release.validate_bundle(archive, [wheel], "current", False, "0.1.0")
    archive, wheel = bundle(tmp_path)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "manifest.json",
            json.dumps(
                {
                    "source_commit": "current",
                    "source_dirty": False,
                    "package_version": "0.1.0",
                    "wheel_sha256": {wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest()},
                }
            ),
        )
        z.writestr("wheels/" + wheel.name, b"changed inside ZIP")
    with pytest.raises(SystemExit, match="integrity"):
        release.validate_bundle(archive, [wheel], "current", False, "0.1.0")


def test_stale_skip_build_cannot_replace_existing_release_output(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    wheels = root / "dist/studio-wheels"
    wheels.mkdir(parents=True)
    archive, _wheel = bundle(wheels, commit="older")
    archive.rename(root / "dist/furnace-studio-preview.zip")
    config = root / "packages/furnace/pyproject.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[project]\nversion = "0.1.0"\n')
    output = root / "dist/release"
    output.mkdir()
    sentinel = output / "reviewed-artifact.txt"
    sentinel.write_text("preserve this")
    monkeypatch.setattr(release, "ROOT", root)
    monkeypatch.setattr(release, "DIST", root / "dist")
    monkeypatch.setattr(release, "OUT", output)
    monkeypatch.setattr(release, "git", lambda *args: "current" if args[0] == "rev-parse" else "")
    monkeypatch.setattr(sys, "argv", ["package_release.py", "--skip-build"])
    with pytest.raises(SystemExit, match="source/version"):
        release.main()
    assert sentinel.read_text() == "preserve this"


def test_untracked_source_requires_explicit_dirty_opt_in(monkeypatch):
    calls = []

    def git(*args):
        calls.append(args)
        return "?? untracked-source.py"

    monkeypatch.setattr(release, "git", git)
    monkeypatch.setattr(sys, "argv", ["package_release.py", "--skip-build"])
    with pytest.raises(SystemExit, match="Commit or stash"):
        release.main()
    assert calls == [("status", "--porcelain")]
