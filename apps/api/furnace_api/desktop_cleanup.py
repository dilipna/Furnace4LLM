"""Explicit, optional uninstall cleanup. Keeps project folders and exports untouched."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from furnace.runtime.cleanup import cleanup
from furnace.runtime.lease import WorkspaceLease


def remove_owned(workspace: Path, records: bool, weights: bool) -> None:
    # Never delete data when Docker cleanup cannot be confirmed.
    report = cleanup(workspace, dry_run=False)
    if report.get("docker"):
        raise RuntimeError("Docker cleanup could not be confirmed; data retained")
    if weights:
        removed = cleanup(workspace, artifacts=workspace / "artifacts", images=True, dry_run=False)
        if removed.get("docker") or any(
            item["status"] == "in_use_or_failed" for item in removed.get("images", [])
        ):
            raise RuntimeError("Optional weight/image cleanup did not complete; records retained")
    if records:
        with WorkspaceLease(workspace):
            for name in ("studio.sqlite3", "studio.sqlite3-wal", "studio.sqlite3-shm"):
                (workspace / name).unlink(missing_ok=True)
            logs = workspace / "logs"
            if logs.exists():
                if logs.is_symlink() or logs.is_junction():
                    raise RuntimeError("Linked log directory retained for manual review")
                shutil.rmtree(logs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", action="store_true")
    parser.add_argument("--weights", action="store_true")
    args = parser.parse_args()
    workspace = Path.home() / ".furnace/studio"
    if any(p.is_symlink() or p.is_junction() for p in (workspace, workspace.parent)):
        raise SystemExit("Linked workspace retained for manual review")
    remove_owned(workspace, args.records, args.weights)


if __name__ == "__main__":
    main()
