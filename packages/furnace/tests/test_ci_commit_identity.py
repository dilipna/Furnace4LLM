"""Exercise CI orchestration with real Git archives and a Docker transport stub."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("loopback_ready", [True, False])
def test_all_jobs_and_pass_stamp_refer_to_the_initial_commit_when_head_moves(
    tmp_path, loopback_ready
):
    bash = Path("C:/Program Files/Git/bin/bash.exe") if sys.platform == "win32" else None
    executable = str(bash) if bash and bash.is_file() else shutil.which("bash")
    if executable is None:
        pytest.skip("bash is required to execute the Linux CI script")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=", "-c", "commit.gpgsign=false", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout.strip()

    git("init", "--quiet")
    markers = [
        "build-marker.txt",
        "apps/web/build-marker.txt",
        "experiments/prefix-cache/build-marker.txt",
    ]
    assets = [
        "apps/api/tests/studio-state.test.mjs",
        "apps/api/tests/everyday-selection.test.mjs",
        "apps/api/furnace_api/studio_assets/studio-state.mjs",
        "apps/api/furnace_api/studio_assets/case-import.mjs",
        "apps/api/furnace_api/studio_assets/everyday-selection.mjs",
    ]
    for name in [*markers, *assets]:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("initial", encoding="utf-8")
    git("add", "-f", ".")
    git(
        "-c",
        "user.name=Furnace test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "initial",
    )
    initial = git("rev-parse", "HEAD")
    for name in markers:
        (repo / name).write_text("changed", encoding="utf-8")
    git("add", "-f", ".")
    git(
        "-c",
        "user.name=Furnace test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "changed",
    )
    changed = git("rev-parse", "HEAD")
    git("checkout", "--quiet", initial)
    # The Linux runner's shared TMPDIR is noexec: source a shell function rather
    # than creating an executable shim there. Python reads the driver as data.
    stub = tmp_path / "docker_env.sh"
    stub.write_text(
        'docker() { "$FURNACE_TEST_PYTHON" "$FURNACE_TEST_DOCKER" "$@"; }\n',
        encoding="utf-8",
        newline="\n",
    )
    driver = tmp_path / "docker_stub.py"
    driver.write_text(
        """import io,json,os,subprocess,sys,tarfile
from pathlib import Path
args=sys.argv[1:]
if args[0]=='port':
 print('127.0.0.1:54321')
elif args[0]=='run' and 'socket.create_connection' in args[-1]:
 sys.exit(0 if os.environ['FURNACE_TEST_LOOPBACK_READY']=='1' else 1)
elif args[0]=='build' and '-f' not in args:
 sys.stdin.buffer.read()  # The toolchain accepts a Dockerfile, not an application tar.
elif args[0]=='build' or '-i' in args:
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read())) as archive:
  values=sorted({archive.extractfile(m).read().decode() for m in archive.getmembers() if m.name.endswith('build-marker.txt')})
 log=Path(os.environ['FURNACE_TEST_ARCHIVES'])
 records=json.loads(log.read_text()) if log.exists() else []
 records.append(values);log.write_text(json.dumps(records))
 if len(records)==1:
  subprocess.run(['git','-c','core.hooksPath=','checkout','--quiet',os.environ['FURNACE_TEST_NEXT_COMMIT']],check=True)
""",
        encoding="utf-8",
    )
    record = tmp_path / "archives.json"
    result = subprocess.run(
        [executable, (ROOT / "scripts/ci_linux.sh").as_posix()],
        cwd=repo,
        env={
            **os.environ,
            "BASH_ENV": stub.as_posix(),
            "FURNACE_TEST_PYTHON": Path(sys.executable).as_posix(),
            "FURNACE_TEST_DOCKER": driver.as_posix(),
            "FURNACE_TEST_ARCHIVES": str(record),
            "FURNACE_TEST_NEXT_COMMIT": changed,
            "FURNACE_TEST_LOOPBACK_READY": "1" if loopback_ready else "0",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert git("rev-parse", "HEAD") == changed, "The test must actually move HEAD during CI"
    if not loopback_ready:
        assert result.returncode != 0
        assert "requires Docker host-loopback networking" in result.stderr
        assert json.loads(record.read_text()) == [["initial"]]
        assert not (repo / ".git/ci-linux-passed").exists()
        return
    assert result.returncode == 0, result.stdout + result.stderr
    actual = {
        "archives": json.loads(record.read_text()),
        "stamp": (repo / ".git/ci-linux-passed").read_text().splitlines(),
    }
    assert actual == {"archives": [["initial"]] * 3, "stamp": [initial]}
