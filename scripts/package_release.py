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
        }
    return list(seen.values())


def check_wheel(wheel: Path) -> None:
    sys.path.insert(0, str(ROOT / "packages/furnace/src"))
    from furnace.runtime.catalog import SUITES

    with zipfile.ZipFile(wheel) as archive:
        for suite in SUITES.values():
            data = archive.read(f"furnace/runtime/suites/{suite.filename}")
            if hashlib.sha256(data).hexdigest() != suite.sha256:
                raise SystemExit(f"packaged suite {suite.id} does not match its pinned digest")
        archive.getinfo("furnace/runtime/pyserve.py")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true", help="reuse dist/ from a build")
    parser.add_argument("--allow-dirty", action="store_true", help="for local experiments only")
    args = parser.parse_args()
    dirty = git("status", "--porcelain", "--untracked-files=no") != ""
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
    check_wheel(next(w for w in wheels if w.name.startswith("furnace-")))
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    name = f"furnace-studio-{version}+{commit[:12]}.zip"
    target = OUT / name
    shutil.copy2(bundle, target)
    files = {name: {"sha256": sha256(target), "bytes": target.stat().st_size}}
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
        "verified_platforms": {
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
