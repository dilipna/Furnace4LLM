"""A version bump must reach the bundle manifest, wheels and executable launcher."""

import hashlib
import importlib.util
import json
import runpy
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "scripts/build_studio_bundle.py"
spec = importlib.util.spec_from_file_location("bundle_version_under_test", SOURCE)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize("versions", [("0.2.0", "0.1.0", "0.1.0"), ("0.3.0", "0.4.0", "0.5.0")])
def test_version_bump_builds_and_launches_the_declared_package_wheels(
    tmp_path, monkeypatch, versions
):
    packages = {
        "furnace": ("packages/furnace", versions[0]),
        "furnace-api": ("apps/api", versions[1]),
        "furnace-bench": ("packages/inference", versions[2]),
    }
    for name, (folder, version) in packages.items():
        config = tmp_path / folder / "pyproject.toml"
        config.parent.mkdir(parents=True)
        config.write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')

    def uv(args, **kwargs):
        if args[1] == "build":
            name = args[args.index("--package") + 1]
            wheel = (
                Path(args[args.index("--out-dir") + 1])
                / f"{name.replace('-', '_')}-{packages[name][1]}-py3-none-any.whl"
            )
            wheel.write_bytes((name + packages[name][1]).encode())
        else:
            Path(args[args.index("--output-file") + 1]).write_text("")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder.shutil, "which", lambda _: str(tmp_path / "uv"))
    monkeypatch.setattr(builder.subprocess, "run", uv)
    monkeypatch.setattr(
        builder.subprocess,
        "check_output",
        lambda args, **kwargs: "commit-sha\n" if "rev-parse" in args else "",
    )
    builder.main()
    install = tmp_path / "installed"
    with zipfile.ZipFile(tmp_path / "dist/furnace-studio-preview.zip") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["package_version"] == versions[0]
        assert manifest["source_commit"] == "commit-sha"
        for name, (_, version) in packages.items():
            filename = f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
            data = archive.read("wheels/" + filename)
            assert hashlib.sha256(data).hexdigest() == manifest["wheel_sha256"][filename]
        for name in archive.namelist():
            target = install / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    commands = []
    monkeypatch.setattr(builder.subprocess, "call", lambda args: commands.append(args) or 0)
    monkeypatch.setattr(sys, "argv", ["launch.py", "--no-browser"])
    with pytest.raises(SystemExit) as exit_status:
        runpy.run_path(str(install / "launch.py"), run_name="__main__")
    assert exit_status.value.code == 0
    command = commands[0]
    for name, (_, version) in packages.items():
        assert (
            str(install / "wheels" / f"{name.replace('-', '_')}-{version}-py3-none-any.whl")
            in command
        )
    assert command[-1] == "--no-browser"
