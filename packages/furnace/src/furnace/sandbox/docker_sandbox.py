"""Docker sandbox for running untrusted repository code.

Two phases:
  1. install: `pip install --target /deps -r <file>` with network access, where <file> is
     the root requirements-dev.txt (the project's own test install, usually including the
     app's requirements with -r) or else requirements.txt, with every -r/-c include that
     stays inside the repository (documented residual risk: dependency install scripts
     run here, isolated from the host and from secrets). Results are cached per hash of
     those files in a named volume.
  2. run: the command executes with no network (or only the internal lab network),
     read-only root filesystem, all capabilities dropped, no-new-privileges,
     pid/memory/cpu limits, a non-root user, and a hard timeout.

The repository is always a disposable *copy*; no secrets or host paths other
than that copy and the dependency volume are mounted.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

IMAGE = "furnace-sandbox-py:0.1"
DOCKERFILE = Path(__file__).parent / "images" / "Dockerfile.python"
LAB_NETWORK = "furnace_furnace-sbx"  # compose network `furnace-sbx` (internal: true)
OUTPUT_LIMIT = 20_000


class SandboxError(Exception):
    pass


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def _docker(
    *args: str, timeout: float = 600, check: bool = True
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["docker", *args],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and proc.returncode != 0:
        raise SandboxError(f"docker {args[0]} failed: {proc.stderr.strip()[-800:]}")
    return proc


def ensure_image() -> None:
    if _docker("image", "inspect", IMAGE, check=False).returncode == 0:
        return
    _docker("build", "-t", IMAGE, "-f", str(DOCKERFILE), str(DOCKERFILE.parent), timeout=900)


# What the sandbox installs, in order of preference: the project's own "install to run the
# tests" file first (it usually includes the app's requirements with -r), then the app's.
REQUIREMENTS_CANDIDATES = ("requirements-dev.txt", "requirements.txt")
MAX_REQUIREMENT_FILES = 20
_INCLUDE_RE = re.compile(r"^\s*(?:-r|--requirement|-c|--constraint)(?:\s+|=)(\S+)")


def requirements_set(repo: Path) -> tuple[str, dict[str, bytes]] | None:
    """(entry file, {repo-relative path: content}) for the dependency install, following
    -r/-c includes. Repository content is untrusted: an include that resolves outside the
    repository (../, an absolute path, a symlink out) is refused, not followed."""
    root = repo.resolve()
    entry = next((n for n in REQUIREMENTS_CANDIDATES if (root / n).is_file()), None)
    if entry is None:
        return None
    files: dict[str, bytes] = {}
    todo = [root / entry]
    while todo:
        p = todo.pop().resolve()
        if not p.is_relative_to(root):
            raise SandboxError("requirements include resolves outside the repository; refused")
        rel = p.relative_to(root).as_posix()
        if rel in files:
            continue
        if not p.is_file():
            raise SandboxError(f"requirements include not found: {rel}")
        if len(files) >= MAX_REQUIREMENT_FILES:
            raise SandboxError(f"more than {MAX_REQUIREMENT_FILES} requirements files included")
        files[rel] = p.read_bytes()
        for line in files[rel].decode("utf-8", errors="replace").splitlines():
            if m := _INCLUDE_RE.match(line):
                todo.append(p.parent / m.group(1))
    return entry, files


def _requirements_digest(files: dict[str, bytes]) -> str:
    if list(files) == ["requirements.txt"]:  # same key as before includes were followed
        return hashlib.sha256(files["requirements.txt"]).hexdigest()[:16]
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode() + b"\0" + files[rel] + b"\0")
    return h.hexdigest()[:16]


def _deps_volume(repo: Path) -> str | None:
    found = requirements_set(repo)
    if found is None:
        return None
    entry, files = found
    vol = f"furnace-deps-{_requirements_digest(files)}"
    if _docker("volume", "inspect", vol, check=False).returncode == 0:
        return vol
    _docker("volume", "create", vol)
    req_dir = Path(tempfile.mkdtemp(prefix="furnace-req-"))
    for rel, data in files.items():  # only the files pip will read, in their layout
        (req_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (req_dir / rel).write_bytes(data)
    # Install phase: network allowed, still unprivileged and resource-limited.
    proc = _docker(
        "run",
        "--rm",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--pids-limit",
        "512",
        "-v",
        f"{req_dir.resolve()}:/req:ro",
        "-v",
        f"{vol}:/deps",
        IMAGE,
        "pip",
        "install",
        "--no-cache-dir",
        "--target",
        "/deps",
        "-r",
        f"/req/{entry}",
        timeout=900,
        check=False,
    )
    shutil.rmtree(req_dir, ignore_errors=True)
    if proc.returncode != 0:
        _docker("volume", "rm", "-f", vol, check=False)
        raise SandboxError(f"dependency install failed: {proc.stderr.strip()[-800:]}")
    return vol


def open_to_sandbox_user(root: Path) -> None:
    """Make the disposable copy readable and writable by the sandbox's uid 10001.

    copytree keeps source modes, so a 0700 source (pytest's tmp_path, mkdtemp) is unreadable
    to the container user on Linux; Docker Desktop on Windows does not enforce this, which hid
    it. Only the copy is opened: its mkdtemp parent stays 0700, so other host users still
    cannot reach it.
    """
    for p in [root, *root.rglob("*")]:
        if p.is_symlink():
            continue
        mode = p.stat().st_mode
        if p.is_dir():
            p.chmod(0o777)
        else:
            p.chmod(0o777 if mode & 0o111 else 0o666)


def run_in_sandbox(
    repo: Path,
    cmd: list[str],
    *,
    network: str = "none",
    timeout_s: float = 300,
    env: dict[str, str] | None = None,
    files: dict[str, str] | None = None,
    output_limit: int = OUTPUT_LIMIT,
) -> SandboxResult:
    """Run `cmd` inside the sandbox against a disposable copy of `repo`.
    `files` (relative path -> text) are written into that copy first; use them to pass
    inputs instead of command-line arguments (argument quoting differs across hosts)."""
    if network not in ("none", LAB_NETWORK):
        raise SandboxError(f"network {network!r} is not allowed")
    ensure_image()
    vol = _deps_volume(repo)
    work = Path(tempfile.mkdtemp(prefix="furnace-sbx-"))
    shutil.copytree(
        repo,
        work / "repo",
        ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__"),
    )
    for rel, text in (files or {}).items():
        target = (work / "repo" / rel).resolve()
        if not target.is_relative_to((work / "repo").resolve()):
            raise SandboxError(f"file path escapes the sandbox copy: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    open_to_sandbox_user(work / "repo")
    name = f"furnace-sbx-{uuid.uuid4().hex[:10]}"
    args = [
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        network,
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=256m",  # noqa: S108 - tmpfs inside the container, not a host path
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--user",
        "10001:10001",
        "-v",
        f"{(work / 'repo').resolve()}:/work",
        "-w",
        "/work",
        "-e",
        "PYTHONPATH=/deps:/work",
        "-e",
        "HOME=/tmp",
    ]
    if vol:
        args += ["-v", f"{vol}:/deps:ro"]
    for k, v in (env or {}).items():
        args += ["-e", f"{k}={v}"]
    args += [IMAGE, *cmd]
    start = time.monotonic()
    timed_out = False
    try:
        proc = _docker(*args, timeout=timeout_s, check=False)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        _docker("kill", name, check=False)
        timed_out, code, out, err = True, -1, "", f"timed out after {timeout_s}s"
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return SandboxResult(
        code, out[-output_limit:], err[-OUTPUT_LIMIT:], time.monotonic() - start, timed_out
    )


def pytest_in_sandbox(
    repo: Path, *targets: str, network: str = "none", timeout_s: float = 300
) -> SandboxResult:
    return run_in_sandbox(
        repo,
        ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets],
        network=network,
        timeout_s=timeout_s,
    )
