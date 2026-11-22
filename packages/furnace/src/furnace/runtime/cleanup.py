"""Remove what Furnace-operated model servers left on this machine, and nothing else.

Refuses while Studio owns the workspace. Removes only containers and networks labelled
for this workspace; optionally the verified-weights store (only its known
subdirectories) and the pinned server/relay images. Model folders, project files,
exports and other Docker resources are never touched. A dry run reports what would go.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from furnace.runtime.catalog import ENGINES, RELAY_IMAGE
from furnace.runtime.lease import WorkspaceLease
from furnace.runtime.manager import RuntimeManager
from furnace.runtime.serving import ServingFault, Supervisor

STORE_PARTS = ("blobs", "partial", "quarantine")


def _size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0


def cleanup(
    workspace: Path,
    artifacts: Path | None = None,
    images: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    report: dict[str, Any] = {"dry_run": dry_run, "containers": [], "networks": []}
    with WorkspaceLease(workspace):
        supervisor = Supervisor(workspace, RuntimeManager(workspace).docker_environment)
        label = f"label=furnace.managed.workspace={supervisor.scope}"
        try:
            listed = supervisor._docker("ps", "--all", "--filter", label, "--format", "{{.Names}}")
            networks = supervisor._docker(
                "network", "ls", "--filter", label, "--format", "{{.Name}}"
            )
            report["containers"] = listed.stdout.split()
            report["networks"] = networks.stdout.split()
            if not dry_run:
                supervisor.recover()
        except ServingFault as exc:
            report["docker"] = exc.code
        if artifacts is not None:
            parts = [artifacts / name for name in STORE_PARTS if (artifacts / name).exists()]
            report["artifacts"] = {
                "path": str(artifacts),
                "bytes": sum(_size(p) for p in parts),
                "folders": [p.name for p in parts],
            }
            if not dry_run:
                for part in parts:
                    shutil.rmtree(part, onerror=_writable_then_retry)
        if images:
            pinned = sorted(
                {*(i for e in ENGINES.values() for i in e.images.values()), RELAY_IMAGE}
            )
            report["images"] = []
            for image in pinned:
                present = supervisor.image_present(image)
                outcome = "absent"
                if present and not dry_run:
                    removed = supervisor._docker("image", "rm", image, check=False, timeout=120)
                    outcome = "removed" if removed.returncode == 0 else "in_use_or_failed"
                elif present:
                    outcome = "present"
                report["images"].append({"image": image, "status": outcome})
    return report


def _writable_then_retry(function: Any, path: str, _info: Any) -> None:
    # Verified blobs are read-only by design; make them writable only to delete them.
    Path(path).chmod(0o600)
    function(path)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="furnace studio-cleanup", description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.home() / ".furnace" / "studio")
    parser.add_argument(
        "--artifacts", type=Path, default=None, help="also remove this weights store"
    )
    parser.add_argument("--images", action="store_true", help="also remove pinned server images")
    parser.add_argument("--yes", action="store_true", help="actually remove (default: dry run)")
    args = parser.parse_args(argv)
    try:
        report = cleanup(args.workspace, args.artifacts, args.images, dry_run=not args.yes)
    except RuntimeError as exc:  # WorkspaceBusy: Studio is running
        print(f"Refused: {exc}")
        return 1
    print(json.dumps(report, indent=2))
    if report["dry_run"]:
        print("Dry run only. Re-run with --yes to remove the items listed above.")
    return 0
