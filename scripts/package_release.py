"""Package a local Studio release candidate with version and integrity information.

    uv run python scripts/package_release.py            # builds, then writes dist/release/

Writes `furnace-studio-<version>+<commit>.zip`, `SHA256SUMS` and `release.json`
(version, exact commit, per-file SHA-256 and size, wheel hashes, verified platforms
read from the recorded validation runs). Refuses a dirty working tree so the
artifact always corresponds to one commit. Nothing is uploaded or published:
publishing is a separate, owner-approved step. Hashes detect corruption; they are
not a publisher signature.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUT = DIST / "release"


def git(*args: str) -> str:
    return subprocess.run(  # noqa: S603 -- fixed git queries in this repository
        ["git", *args],  # noqa: S607 -- git from PATH, as every repository script uses
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def verified_platforms() -> list[dict[str, str]]:
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for record in sorted((ROOT / "docs/product/verification").glob("real-model-*.json")):
        data = json.loads(record.read_text(encoding="utf-8"))
        if data.get("result") != "passed":
            continue
        env = data["environment"]
        key = (env["os"].split(" (")[0], data["accelerator"])
        seen[key] = {
            "os": key[0],
            "docker": f"{env.get('docker_os')} {env.get('docker_server')}",
            "accelerator": data["accelerator"],
            "evidence": record.relative_to(ROOT).as_posix(),
            "evidence_commit": env.get("furnace_commit", "not recorded"),
        }
    return list(seen.values())


def validate_bundle(
    bundle: Path, wheels: list[Path], commit: str, dirty: bool, version: str
) -> None:
    """Refuse stale or inconsistent inputs before replacing any release output."""
    try:
        with zipfile.ZipFile(bundle) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest must be an object")
            if (
                manifest.get("source_commit") != commit
                or type(manifest.get("source_dirty")) is not bool
                or manifest["source_dirty"] != dirty
                or manifest.get("package_version") != version
            ):
                raise SystemExit(
                    "Preview source/version differs from this checkout; rebuild first."
                )
            expected = manifest.get("wheel_sha256")
            if (
                not isinstance(expected, dict)
                or not expected
                or set(expected) != {w.name for w in wheels}
            ):
                raise SystemExit(
                    "Preview wheel inventory differs from dist/studio-wheels; rebuild first."
                )
            for wheel in wheels:
                embedded = hashlib.sha256(archive.read("wheels/" + wheel.name)).hexdigest()
                if embedded != expected[wheel.name] or sha256(wheel) != expected[wheel.name]:
                    raise SystemExit("Preview wheel integrity mismatch; rebuild first.")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        raise SystemExit("Preview bundle is missing or invalid; rebuild first.") from None


def check_wheel(wheel: Path) -> None:
    sys.path.insert(0, str(ROOT / "packages/furnace/src"))
    from furnace.runtime.catalog import SUITES

    with zipfile.ZipFile(wheel) as archive:
        for suite in SUITES.values():
            data = archive.read(f"furnace/runtime/suites/{suite.filename}")
            if hashlib.sha256(data).hexdigest() != suite.sha256:
                raise SystemExit(f"packaged suite {suite.id} does not match its pinned digest")
        archive.getinfo("furnace/runtime/pyserve.py")


def validate_windows(metadata: Path, commit: str, version: str) -> tuple[Path, dict]:
    try:
        data = json.loads(metadata.read_text())
        name = data["file"]
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not name.endswith("-windows-x64.exe")
        ):
            raise ValueError("invalid filename")
        binary = metadata.parent / name
        if (
            data["commit"] != commit
            or data["version"] != version
            or data.get("source_dirty") is not False
        ):
            raise ValueError("source/version mismatch")
        if data["bytes"] != binary.stat().st_size or data["sha256"] != sha256(binary):
            raise ValueError("integrity mismatch")
        return binary, data
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "Windows installer source/version/integrity is invalid; rebuild first."
        ) from None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true", help="reuse dist/ from a build")
    parser.add_argument("--allow-dirty", action="store_true", help="for local experiments only")
    parser.add_argument(
        "--windows", type=Path, help="include this installer.json after verifying source and bytes"
    )
    args = parser.parse_args()
    dirty = git("status", "--porcelain") != ""
    if dirty and not args.allow_dirty:
        raise SystemExit("Commit or stash changes first: a release must match one commit.")
    commit = git("rev-parse", "HEAD")
    version = tomllib.loads((ROOT / "packages/furnace/pyproject.toml").read_text())["project"][
        "version"
    ]
    if not args.skip_build:
        subprocess.run(  # noqa: S603 -- the repository's own build script
            [sys.executable, str(ROOT / "scripts/build_studio_bundle.py")], cwd=ROOT, check=True
        )
    bundle = DIST / "furnace-studio-preview.zip"
    wheels = sorted((DIST / "studio-wheels").glob("*.whl"))
    validate_bundle(bundle, wheels, commit, dirty, version)
    windows = validate_windows(args.windows, commit, version) if args.windows else None
    if windows and dirty:
        raise SystemExit("Windows distribution requires a clean checkout.")
    check_wheel(next(w for w in wheels if w.name.startswith("furnace-")))
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    name = f"furnace-studio-{version}+{commit[:12]}.zip"
    target = OUT / name
    shutil.copy2(bundle, target)
    files = {name: {"sha256": sha256(target), "bytes": target.stat().st_size}}
    if windows:
        binary, info = windows
        shutil.copy2(binary, OUT / binary.name)
        shutil.copy2(args.windows, OUT / "installer.json")
        files[binary.name] = {"sha256": info["sha256"], "bytes": info["bytes"]}
    (OUT / "SHA256SUMS").write_text(
        "".join(f"{info['sha256']}  {file}\n" for file, info in files.items()),
        encoding="utf-8",
        newline="\n",
    )
    release = {
        "schema": "furnace-release-candidate-v1",
        "version": version,
        "commit": commit,
        "working_tree_clean": not dirty,
        "built_at": datetime.now(UTC).isoformat(),
        "files": files,
        "wheels": {w.name: sha256(w) for w in wheels},
        "requires": "Python 3.12 and uv; Docker with Linux containers for model servers",
        "windows_installer": windows[1] if windows else None,
        "verified_platforms": {
            "evidence_scope": "Historical recorded runs; not validation of this release ZIP.",
            "workspace_and_free_kit": "Windows 11 and Linux (installed-bundle checks)",
            "furnace_operated_model_servers": verified_platforms(),
            "not_verified": ["macOS", "fresh Windows user profile", "Linux host real-model runs"],
        },
        "integrity": "SHA-256 detects corruption; this is not a publisher signature.",
        "published": False,
    }
    (OUT / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    print(f"{target.relative_to(ROOT)}  sha256 {files[name]['sha256']}")


if __name__ == "__main__":
    main()
