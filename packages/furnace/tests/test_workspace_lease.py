import subprocess
import sys

import pytest
from furnace.runtime.lease import WorkspaceLease


def test_another_process_cannot_open_a_live_workspace(tmp_path):
    code = "from pathlib import Path; from furnace.runtime.lease import WorkspaceLease; import sys; lease=WorkspaceLease(Path(sys.argv[1])); lease.__enter__()"
    with WorkspaceLease(tmp_path):
        blocked = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=10
        )
        assert blocked.returncode != 0 and "already open" in blocked.stderr
    allowed = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=10
    )
    assert allowed.returncode == 0, allowed.stderr


def test_crashed_process_releases_ownership(tmp_path):
    # Exit the interpreter abruptly, without context-manager/finalizer cleanup.
    # Killing Windows' venv launcher alone can return before its interpreter exits.
    code = "from pathlib import Path; from furnace.runtime.lease import WorkspaceLease; import os,sys; lease=WorkspaceLease(Path(sys.argv[1])); lease.__enter__(); print('owned',flush=True); os._exit(17)"
    crashed = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert crashed.stdout.strip() == "owned" and crashed.returncode == 17, crashed.stderr
    with WorkspaceLease(tmp_path):
        pass


def test_exception_releases_workspace_lease(tmp_path):
    with pytest.raises(ValueError), WorkspaceLease(tmp_path):
        raise ValueError("test failure")
    with WorkspaceLease(tmp_path):
        pass
