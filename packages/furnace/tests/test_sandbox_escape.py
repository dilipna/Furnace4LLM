"""Escape attempts against the real Docker sandbox: what untrusted repository code can NOT do.

Requires Docker (like the other sandbox tests). The lab-network test runs only when the
compose network exists.
"""

import json
import subprocess
import sys

import pytest
from furnace.sandbox.docker_sandbox import LAB_NETWORK, SandboxError, run_in_sandbox

PROBE = r"""
import json, os, socket

def attempt(fn):
    try:
        fn()
        return "allowed"
    except Exception as exc:
        return f"blocked: {type(exc).__name__}"

def tcp(host, port):
    s = socket.create_connection((host, port), timeout=3)
    s.close()

def write_root():
    with open("/furnace_escape_test", "w") as f:
        f.write("x")

def setuid_root():
    os.setuid(0)

print(json.dumps({
    "uid": os.getuid(),
    "tcp_public_ip": attempt(lambda: tcp("1.1.1.1", 443)),
    "dns": attempt(lambda: socket.getaddrinfo("github.com", 443)),
    "write_root_fs": attempt(write_root),
    "setuid_root": attempt(setuid_root),
    "write_workdir": attempt(lambda: open("/work/ok.txt", "w").write("x")),
}))
"""


def _probe(tmp_path, network="none"):
    r = run_in_sandbox(
        tmp_path, ["python", "probe.py"], network=network, files={"probe.py": PROBE}, timeout_s=60
    )
    assert r.exit_code == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_untrusted_code_cannot_reach_out_or_escalate(tmp_path):
    out = _probe(tmp_path)
    assert out["uid"] == 10001
    assert out["tcp_public_ip"].startswith("blocked")
    assert out["dns"].startswith("blocked")
    assert out["write_root_fs"].startswith("blocked")
    assert out["setuid_root"].startswith("blocked")
    assert out["write_workdir"] == "allowed"  # only the disposable repo copy is writable


def _lab_network_exists() -> bool:
    r = subprocess.run(
        ["docker", "network", "inspect", LAB_NETWORK], capture_output=True, check=False
    )
    return r.returncode == 0


@pytest.mark.skipif(not _lab_network_exists(), reason="compose lab network not created")
def test_lab_network_has_no_internet(tmp_path):
    out = _probe(tmp_path, network=LAB_NETWORK)
    assert out["tcp_public_ip"].startswith("blocked")
    assert out["uid"] == 10001


def test_other_networks_and_path_escapes_are_refused(tmp_path):
    with pytest.raises(SandboxError, match="not allowed"):
        run_in_sandbox(tmp_path, ["python", "-c", "1"], network="bridge")
    with pytest.raises(SandboxError, match="escapes"):
        run_in_sandbox(tmp_path, ["python", "-c", "1"], files={"../outside.py": "x"})


def test_timeout_is_enforced(tmp_path):
    r = run_in_sandbox(tmp_path, ["python", "-c", "import time; time.sleep(30)"], timeout_s=3)
    assert r.timed_out and not r.ok


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_disposable_copy_is_opened_to_the_sandbox_user(tmp_path):
    """Regression (Linux CI): a 0700 source made the copy unreadable to uid 10001."""
    from furnace.sandbox.docker_sandbox import open_to_sandbox_user

    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("x = 1\n")
    (root / "run.sh").write_text("#!/bin/sh\n")
    (root / "run.sh").chmod(0o700)
    root.chmod(0o700)
    open_to_sandbox_user(root)
    assert root.stat().st_mode & 0o777 == 0o777
    assert (root / "pkg").stat().st_mode & 0o777 == 0o777
    assert (root / "pkg" / "a.py").stat().st_mode & 0o777 == 0o666
    assert (root / "run.sh").stat().st_mode & 0o777 == 0o777
