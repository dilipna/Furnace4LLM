"""Inspect the actual installer input tree; the compiler/dependency tools are stubs."""

import importlib.util
import sys
from pathlib import Path


def test_native_build_includes_project_notice_without_removing_runtime_notices(
    tmp_path, monkeypatch
):
    source = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "native_notice_build", source / "scripts/build_windows.py"
    )
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    notice = (source / "LICENSE").read_bytes()
    (tmp_path / "LICENSE").write_bytes(notice)
    icon = tmp_path / "packaging/windows/furnace.ico"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"test icon")
    for folder, name in [
        ("packages/furnace", "furnace"),
        ("packages/inference", "furnace-bench"),
        ("apps/api", "furnace-api"),
    ]:
        config = tmp_path / folder / "pyproject.toml"
        config.parent.mkdir(parents=True)
        config.write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n')
    base = tmp_path / "python-base"
    for folder in ("DLLs", "Lib", "tcl"):
        (base / folder).mkdir(parents=True)
    (base / "python.exe").write_bytes(b"test runtime")
    (base / "LICENSE.txt").write_bytes(b"runtime notice retained")
    out = tmp_path / "dist/windows"
    commit = "a" * 40

    def run(*args):
        if args[0] == "git":
            return commit if args[1] == "rev-parse" else ""
        if args[0] == "powershell":
            return "NotSigned"
        if args[0] == "uv" and args[1] == "build":
            package = args[args.index("--package") + 1].replace("-", "_")
            (out / "wheels" / f"{package}-0.1.0-py3-none-any.whl").write_bytes(b"test wheel")
        elif args[0] == "uv" and args[1] == "export":
            Path(args[args.index("--output-file") + 1]).write_text("")
        elif args[0] == "iscc":
            (out / f"Furnace-0.1.0-{commit[:12]}-windows-x64.exe").write_bytes(b"test installer")
            return "Inno Setup 6.4.3"
        return ""

    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "OUT", out)
    monkeypatch.setattr(builder, "run", run)
    monkeypatch.setattr(builder.shutil, "which", lambda name: name)
    monkeypatch.setattr(sys, "base_prefix", str(base))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "version_info", (3, 12, 13))
    monkeypatch.setattr(sys, "argv", ["build_windows.py", "--iscc", "iscc"])
    monkeypatch.setenv("FURNACE_VERIFY_BINARY", "")
    builder.main()
    assert (out / "app/LICENSE").read_bytes() == notice
    assert (out / "app/runtime/LICENSE.txt").read_bytes() == b"runtime notice retained"
