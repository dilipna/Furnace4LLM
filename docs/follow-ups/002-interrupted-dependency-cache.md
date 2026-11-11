# Local issue 002: dependency-cache reuse after interrupted installation

Status: open; recorded during the Guard retry review, not implemented in that change.

Affected path: `packages/furnace/src/furnace/sandbox/docker_sandbox.py`, `_deps_volume`.

Reproduction (a mocked timeout, no real 900-second wait): run the following with the repository's Python environment. It calls the real cache function and replaces only the Docker command and staged requirements path.

```python
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from furnace.sandbox import docker_sandbox as sb

state = {"exists": False, "installs": 0}


def docker(*args, **kwargs):
    if args[:2] == ("volume", "inspect"):
        return subprocess.CompletedProcess(args, 0 if state["exists"] else 1, "", "")
    if args[:2] == ("volume", "create"):
        state["exists"] = True
        return subprocess.CompletedProcess(args, 0, "", "")
    if args[0] == "run":
        state["installs"] += 1
        raise subprocess.TimeoutExpired("pip install", 900)
    raise AssertionError(args)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "requirements.txt").write_text("example==1.0\n")
    with (
        patch.object(sb, "_docker", docker),
        patch.object(sb, "stage_requirements", return_value=root / "staged"),
    ):
        try:
            sb._deps_volume(root)
        except subprocess.TimeoutExpired:
            pass
        print(sb._deps_volume(root), state)
```

Observed: the retry returns a cache volume with `installs == 1`, despite installation having timed out. The function creates the volume before pip runs, treats existence as success, and does not handle timeout cleanup. This confirms host control flow with a mocked failure; an actual container installation timeout was not induced. Concurrent initialization is suspected from inspection and is not claimed as reproduced.

Expected: a dependency cache is reusable only after successful installation. Interrupted initialization must leave a retryable state, and installation resources must be cleaned up even when subprocess execution raises.

Acceptance criteria:

- Reproduce timeout/exception and nonzero exit; retry actually installs instead of accepting partial contents.
- Successful completed installs remain reusable without reinstalling.
- Clean staged files and terminate any still-running installation container on timeout.
- Do not delete or mutate a cache currently being installed or consumed by another caller; add a concurrent initialization test for the chosen design.
- Retain existing dependency hashes, sandbox privilege/network boundaries and failure diagnostics, or document a justified versioned migration of cache keys.
- Avoid new services or dependencies unless demonstrably necessary.
