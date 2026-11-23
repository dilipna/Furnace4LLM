"""Test-only pipe protocol; run with the installed interpreter, never a public endpoint."""

import json
import sys
from pathlib import Path

from furnace.runtime.lease import WorkspaceLease
from furnace_api import desktop

app, workspace = map(Path, sys.argv[1:3])
assert Path(desktop.__file__).resolve().is_relative_to(app.resolve())
service = desktop.DesktopService(workspace, Path(sys.argv[3]) if len(sys.argv) > 3 else None)
service.start()
# The caller reads this through a private pipe and never persists the session URL/token.
print(
    json.dumps(
        {
            "url": service.url,
            "token": service.token,
            "installed_module": str(Path(desktop.__file__).relative_to(app)),
        }
    ),
    flush=True,
)
try:
    sys.stdin.readline()
finally:
    assert service.stop(), "Studio did not finish cleanup"
with WorkspaceLease(workspace):
    pass
print(json.dumps({"stopped": True, "lease_released": True}), flush=True)
