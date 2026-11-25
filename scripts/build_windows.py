"""Build a per-user Windows installer; no downloads happen on the end user's first launch.

Build machine: uv-managed CPython 3.12.13, uv and Inno Setup 6.4.3.
The compiler is pinned to a free-use version. Nothing is published by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/windows"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str) -> str:
    return subprocess.check_output(list(args), cwd=ROOT, text=True).strip()  # noqa: S603 -- developer build, explicit argv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", type=Path, required=True)
    parser.add_argument(
        "--sign-command", help="Configured Inno signing command; omit for unsigned builds"
    )
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info[:3] != (3, 12, 13):
        raise SystemExit("Build with uv-managed Windows CPython 3.12.13.")
    if run("git", "status", "--porcelain"):
        raise SystemExit("Commit changes first; installers must identify clean source.")
    version = tomllib.loads((ROOT / "packages/furnace/pyproject.toml").read_text())["project"][
        "version"
    ]
    commit = run("git", "rev-parse", "HEAD")
    stage = OUT / "app"
    # Only this builder's generated directory may be replaced.
    assert stage.resolve().is_relative_to((ROOT / "dist").resolve())
    shutil.rmtree(stage, ignore_errors=True)
    runtime = stage / "runtime"
    base = Path(sys.base_prefix)
    runtime.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging/windows/furnace.ico", stage / "furnace.ico")
    for name in ("DLLs", "Lib", "tcl"):
        shutil.copytree(
            base / name,
            runtime / name,
            ignore=shutil.ignore_patterns(
                "__pycache__", "site-packages", "test", "tests", "idlelib"
            ),
        )
    for file in base.iterdir():
        if file.suffix.lower() in {".exe", ".dll", ".txt"} or file.name == "BUILD":
            shutil.copy2(file, runtime / file.name)
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required on the build machine, not the end user's machine.")
    wheels = OUT / "wheels"
    wheels.mkdir(exist_ok=True)
    names = []
    for package in ("furnace-bench", "furnace", "furnace-api"):
        run(uv, "build", "--package", package, "--wheel", "--out-dir", str(wheels))
    # Use only newly declared versions, never stale wheels from another version.
    for folder in ("packages/inference", "packages/furnace", "apps/api"):
        project = tomllib.loads((ROOT / folder / "pyproject.toml").read_text())["project"]
        names.append(
            wheels / f"{project['name'].replace('-', '_')}-{project['version']}-py3-none-any.whl"
        )
    requirements = OUT / "requirements.txt"
    run(
        uv,
        "export",
        "--package",
        "furnace-api",
        "--frozen",
        "--no-dev",
        "--no-header",
        "--no-emit-workspace",
        "--output-file",
        str(requirements),
    )
    target = runtime / "Lib/site-packages"
    run(
        uv,
        "pip",
        "install",
        "--python",
        str(runtime / "python.exe"),
        "--target",
        str(target),
        "--require-hashes",
        "--no-deps",
        "-r",
        str(requirements),
    )
    run(
        uv,
        "pip",
        "install",
        "--python",
        str(runtime / "python.exe"),
        "--target",
        str(target),
        "--no-deps",
        *map(str, names),
    )
    run(
        str(runtime / "python.exe"),
        "-I",
        "-c",
        "import tkinter, furnace_api.desktop, furnace.runtime.catalog",
    )
    manifest = {
        "schema": "furnace-windows-installer-v1",
        "version": version,
        "commit": commit,
        "built_at": datetime.now(UTC).isoformat(),
        "published": False,
        "source_dirty": False,
        "platform": "windows-x64",
        "experience": "researcher-infrastructure-preview",
        "python": sys.version.split()[0],
        "compiler": "Inno Setup 6.4.3",
        "signed": bool(args.sign_command),
        "wheel_sha256": {p.name: digest(p) for p in names},
        "reproducibility": "Repeatable pinned-input recipe; binary identity is not established (PE timestamps/signing).",
    }
    (stage / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy2(requirements, stage / "requirements.txt")
    command = [
        str(args.iscc),
        f"/DAppVersion={version}",
        f"/DSourceCommit={commit}",
        f"/DStage={stage}",
        f"/DOutput={OUT}",
    ]
    if args.sign_command:
        command += ["/DSignBuild", "/Sfurnace=" + args.sign_command]
    command.append(str(ROOT / "packaging/windows/furnace.iss"))
    compiler_output = run(*command)
    if "6.4.3" not in compiler_output:
        raise SystemExit("Use the pinned Inno Setup 6.4.3 compiler.")
    installer = OUT / f"Furnace-{version}-{commit[:12]}-windows-x64.exe"
    if run("git", "rev-parse", "HEAD") != commit or run("git", "status", "--porcelain"):
        raise SystemExit("Source changed during the build; rebuild from a clean commit.")
    os.environ["FURNACE_VERIFY_BINARY"] = str(installer.resolve())
    signature = run(
        "powershell",
        "-NoProfile",
        "-Command",
        "$env:PSModulePath=Join-Path $PSHOME 'Modules'; Import-Module Microsoft.PowerShell.Security -ErrorAction Stop; (Get-AuthenticodeSignature -LiteralPath $env:FURNACE_VERIFY_BINARY).Status",
    )
    if args.sign_command and signature != "Valid":
        raise SystemExit("Signing was requested but Authenticode is not valid.")
    manifest.update(
        file=installer.name,
        bytes=installer.stat().st_size,
        sha256=digest(installer),
        signed=signature == "Valid",
        signature_status=signature,
    )
    (OUT / "installer.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "SHA256SUMS").write_text(f"{manifest['sha256']}  {installer.name}\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
