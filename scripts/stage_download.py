"""Stage the actual installer for an unpublished local/static preview, never upload it."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "dist/windows"
metadata = json.loads((source / "installer.json").read_text())
name = metadata["file"]
assert Path(name).name == name and name.endswith(".exe")
binary = source / name
assert binary.stat().st_size == metadata["bytes"]
assert hashlib.sha256(binary.read_bytes()).hexdigest() == metadata["sha256"]
target = ROOT / "apps/web/public/downloads"
target.mkdir(parents=True, exist_ok=True)
shutil.copy2(binary, target / name)
shutil.copy2(source / "installer.json", target / "installer.json")
shutil.copy2(source / "SHA256SUMS", target / "SHA256SUMS")
print("Staged unpublished installer", name)
