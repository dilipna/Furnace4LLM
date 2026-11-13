"""Build the local Studio preview bundle from workspace wheels; never include user data."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    wheels = ROOT / "dist" / "studio-wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    executable = shutil.which("uv")
    if executable is None:
        raise SystemExit("Install uv before building Studio")
    names = []
    for package in ("furnace-bench", "furnace", "furnace-api"):
        subprocess.run(  # noqa: S603 -- resolved uv, authored package names; no shell
            [executable, "build", "--package", package, "--wheel", "--out-dir", str(wheels)],
            cwd=ROOT,
            check=True,
        )
        names.append(package.replace("-", "_") + "-0.1.0-py3-none-any.whl")
    subprocess.run(  # noqa: S603 -- fixed export arguments and workspace path
        [
            executable,
            "export",
            "--frozen",
            "--no-dev",
            "--no-header",
            "--no-emit-workspace",
            "--no-editable",
            "--output-file",
            str(wheels / "requirements.txt"),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    launcher = """from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
root = Path(__file__).resolve().parent
wheels = root / 'wheels'
manifest = json.loads((root / 'manifest.json').read_text())
for name, expected in manifest['wheel_sha256'].items():
    if Path(name).name != name or hashlib.sha256((wheels / name).read_bytes()).hexdigest() != expected:
        raise SystemExit('Wheel integrity check failed; extract a fresh bundle')
uv = shutil.which('uv')
if uv is None:
    raise SystemExit('Furnace needs uv to create its isolated environment. Install uv, reopen your terminal and run python launch.py again. See README.md for prerequisites.')
command = [uv, 'tool', 'run', '--python', '3.12', '--with-requirements', str(root / 'requirements.txt'), '--from', str(wheels / 'furnace_api-0.1.0-py3-none-any.whl'), '--with', str(wheels / 'furnace-0.1.0-py3-none-any.whl'), '--with', str(wheels / 'furnace_bench-0.1.0-py3-none-any.whl'), 'furnace-studio', *sys.argv[1:]]
try:
    raise SystemExit(subprocess.call(command))
except KeyboardInterrupt:
    raise SystemExit(130) from None
"""
    readme = """# Furnace Studio — local application preview

Prerequisites: Python 3.12 and uv installed. Extract this ZIP to a new folder.
Run: python launch.py
Or: python launch.py --no-browser --workspace PATH --port 8787

First launch installs pinned dependencies from public package registries and may
obtain Python through uv. No model weights are downloaded. Keep the terminal open;
Ctrl+C stops Studio. Open the private local session link printed by the launcher.
The app binds only to 127.0.0.1. Never share its session link or expose its port.
Default local storage: ~/.furnace/studio (project metadata, cases and preferences).
Projects must be folders on the machine running Studio. Model source is not altered.

First visit: choose Open guided example to explore without a model folder or GPU.
It contains metadata and two prepared cases, not a trained model. Opening it starts
nothing. Follow Your next step, check the environment, prepare the local test image,
then select the fixture and approve execution. One case checks exact output; the
other demonstrates why descriptive expectations remain unscored. The environment
check is read-only: it never downloads images, starts workers or verifies a model.
You can inspect and export the example even without Docker installed.

This is a wheel-based preview requiring Python/uv, not a native one-click installer.
Free assessment, starter-kit export and local workspace persistence are implemented.
The $20/month managed-service offer supports both compute ownership choices in
configuration. Billing and cloud provisioning are inactive. No research-model adapter
is validated. Optional local Docker execution runs ONLY a deterministic infrastructure
fixture, not a learned model. Prepare the local test environment, save preferences,
select the fixture and approve its execution. It uses 256 MiB, one CPU, no network,
no ports, a read-only root and no model-folder or credential mounts. Preparation may
download public image/dependency packages. Remote Docker contexts are refused.
Exact-output evaluations execute against this fixture; descriptive cases are unscored.
Failures/timeouts stop the worker; restart explicitly. Stop Studio normally for cleanup;
after a crash reopen the same workspace to reconcile its owned worker. One Studio
process may own a workspace. No real model inference or quality evidence is included.

Do not enter secrets or production input data. Project configuration and evaluation
examples are saved locally and included in starter-kit exports. Workspace activity
records configuration and framework request metadata, not raw request/output logs. Source file detection is not security,
quality or architecture verification. Test with real models after application review.

Remove a project through Activity to delete only its workspace record. Uninstall:
stop the process, remove this extracted folder and (if desired) the dedicated workspace
folder after reviewing retention. Do not delete shared model folders or uv caches.
"""
    git = shutil.which("git")
    if git is None:
        raise SystemExit("Git is required to record preview source provenance")
    source_commit = subprocess.check_output([git, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()  # noqa: S603 -- resolved git, fixed read-only arguments
    status = subprocess.check_output([git, "status", "--porcelain"], cwd=ROOT, text=True)  # noqa: S603 -- resolved git, fixed read-only arguments
    source_dirty = bool(status)
    manifest = {
        "source_commit": source_commit,
        "source_dirty": source_dirty,
        "package_version": "0.1.0",
        "kind": "local_application_preview",
        "model_execution": False,
        "billing": "inactive",
        "wheel_sha256": {
            name: hashlib.sha256((wheels / name).read_bytes()).hexdigest() for name in names
        },
    }
    archive_path = ROOT / "dist" / "furnace-studio-preview.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(wheels / name, "wheels/" + name)
        archive.write(wheels / "requirements.txt", "requirements.txt")
        archive.writestr("launch.py", launcher)
        archive.writestr("README.md", readme)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    print(archive_path)


if __name__ == "__main__":
    main()
