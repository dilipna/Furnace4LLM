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
    code = "from pathlib import Path; from furnace.runtime.lease import WorkspaceLease; import sys,time; lease=WorkspaceLease(Path(sys.argv[1])); lease.__enter__(); print('owned',flush=True); time.sleep(60)"
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "owned"
        child.kill()
        child.wait(timeout=10)
        with WorkspaceLease(tmp_path):
            pass
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)


def test_exception_releases_workspace_lease(tmp_path):
    with pytest.raises(ValueError), WorkspaceLease(tmp_path):
        raise ValueError("test failure")
    with WorkspaceLease(tmp_path):
        pass
