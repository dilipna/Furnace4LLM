"""Real Docker cache publication, interruption and concurrency; no external packages."""

import concurrent.futures
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile

import pytest
from furnace.sandbox import dependency_cache as cache
from furnace.sandbox import docker_sandbox as sb


@pytest.fixture
def local_cache(tmp_path, monkeypatch):
    sb.ensure_image()
    image = cache.image_identity(sb.IMAGE, sb._docker)
    wheel = tmp_path / "furnace_cache_probe-0.0.1-py3-none-any.whl"
    dist = "furnace_cache_probe-0.0.1.dist-info/"
    contents = {
        "cache_probe.py": "VALUE = 'complete-local-wheel'\n",
        dist + "METADATA": "Metadata-Version: 2.1\nName: furnace-cache-probe\nVersion: 0.0.1\n",
        dist
        + "WHEEL": "Wheel-Version: 1.0\nGenerator: furnace-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    contents[dist + "RECORD"] = "\n".join(name + ",," for name in [*contents, dist + "RECORD"])
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text(f"--no-index\n/req/{wheel.name}\n# {uuid.uuid4().hex}\n")
    files = (sb.requirements_set(repo) or ("", {}))[1]
    key = cache.cache_key("requirements.txt", files, image)
    docker, original_stage = sb._docker, sb.stage_requirements
    volumes, installers, stages = [], [], []
    guard = threading.Lock()

    def stage(requirements):
        directory = original_stage(requirements)
        shutil.copyfile(wheel, directory / wheel.name)
        stages.append(directory)
        return directory

    def tracked(*args, **kwargs):
        with guard:
            if args[:2] == ("volume", "create"):
                volumes.append(args[-1])
            if args[0] == "run" and "pip" in args:
                installers.append(args[args.index("--name") + 1])
        return docker(*args, **kwargs)

    monkeypatch.setattr(sb, "stage_requirements", stage)
    try:
        yield repo, image, key, docker, tracked, volumes, installers, stages
    finally:
        for name in installers:
            docker("rm", "-f", name, check=False, timeout=30)
        docker("rm", "-f", "furnace-deps-v2-ready-" + key, check=False, timeout=30)
        for volume in volumes:
            docker("volume", "rm", volume, check=False, timeout=30)
        for directory in stages:
            shutil.rmtree(directory, ignore_errors=True)


def test_real_timeout_cleans_install_and_retry_imports_complete_package(local_cache, monkeypatch):
    repo, image, key, docker, tracked, volumes, installers, stages = local_cache
    first = True

    def interrupted(*args, **kwargs):
        nonlocal first
        if args[0] == "run" and "pip" in args and first:
            first = False
            prefix = list(args[: args.index("pip")])
            # The controlled install phase writes partial data, then pauses before pip.
            args = (
                *prefix,
                "python",
                "-I",
                "-S",
                "-c",
                "from pathlib import Path; import time; Path('/deps/partial').write_text('partial'); time.sleep(30)",
            )
            installers.append(args[args.index("--name") + 1])
            kwargs["timeout"] = 2
        return tracked(*args, **kwargs)

    monkeypatch.setattr(sb, "_docker", interrupted)
    with pytest.raises(subprocess.TimeoutExpired):
        sb._deps_volume(repo)
    assert docker("container", "inspect", installers[0], check=False).returncode != 0
    assert (
        docker("container", "inspect", "furnace-deps-v2-ready-" + key, check=False).returncode != 0
    )
    assert all(not directory.exists() for directory in stages)
    selected = sb._deps_volume(repo)
    assert len(volumes) == 2 and selected == volumes[1]
    result = sb.run_in_sandbox(
        repo, ["python", "-c", "import cache_probe; print(cache_probe.VALUE)"], timeout_s=15
    )
    assert result.ok and result.stdout.strip() == "complete-local-wheel"
    assert len(volumes) == 2  # Reuse requires neither a new candidate nor another install.
    assert (
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{selected}:/deps:ro",
            image,
            "python",
            "-c",
            "from pathlib import Path; assert not Path('/deps/partial').exists()",
            check=False,
        ).returncode
        == 0
    )


def test_two_real_initializers_publish_one_complete_cache_without_partial_reads(
    local_cache, monkeypatch
):
    repo, _image, _key, docker, tracked, volumes, installers, stages = local_cache
    gate = threading.Barrier(2)

    def concurrent_docker(*args, **kwargs):
        if args[0] == "run" and "pip" in args:
            gate.wait(timeout=20)
        return tracked(*args, **kwargs)

    monkeypatch.setattr(sb, "_docker", concurrent_docker)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(sb._deps_volume, repo) for _ in range(2)]
        selected = [future.result(timeout=60) for future in futures]
    assert len(volumes) == len(installers) == 2
    assert selected[0] == selected[1]
    assert all(not directory.exists() for directory in stages)
    assert all(
        docker("container", "inspect", name, check=False).returncode != 0 for name in installers
    )
    assert (
        sum(docker("volume", "inspect", volume, check=False).returncode == 0 for volume in volumes)
        == 1
    )
    result = sb.run_in_sandbox(
        repo, ["python", "-c", "import cache_probe; print(cache_probe.VALUE)"], timeout_s=15
    )
    assert result.ok and "complete-local-wheel" in result.stdout


def test_failed_overlapping_initializer_does_not_disrupt_active_consumer(local_cache, monkeypatch):
    repo, image, key, docker, tracked, volumes, installers, _stages = local_cache
    gate, release = threading.Barrier(2), threading.Event()
    counter, guard = 0, threading.Lock()

    def overlap(*args, **kwargs):
        nonlocal counter
        if args[0] == "run" and "pip" in args:
            with guard:
                counter += 1
                index = counter
            gate.wait(timeout=20)
            if index == 2:
                assert release.wait(timeout=30)
                installers.append(args[args.index("--name") + 1])
                args = (*args[: args.index("pip")], "python", "-c", "import sys; sys.exit(7)")
        return tracked(*args, **kwargs)

    monkeypatch.setattr(sb, "_docker", overlap)
    consumer = "furnace-cache-consumer-" + uuid.uuid4().hex
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(sb._deps_volume, repo) for _ in range(2)]
            done, _ = concurrent.futures.wait(
                pending, timeout=40, return_when=concurrent.futures.FIRST_COMPLETED
            )
            assert len(done) == 1
            volume = next(iter(done)).result()
            assert cache.ready_volume(key, image, docker) == volume
            docker(
                "run",
                "-d",
                "--name",
                consumer,
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--user",
                "10001:10001",
                "-v",
                f"{volume}:/deps:ro",
                "-e",
                "PYTHONPATH=/deps",
                image,
                "python",
                "-c",
                "import cache_probe,time; assert cache_probe.VALUE=='complete-local-wheel'; time.sleep(60)",
            )
            release.set()
            results = []
            for future in pending:
                try:
                    results.append(future.result(timeout=30))
                except sb.SandboxError:
                    results.append(None)
            assert results.count(volume) == results.count(None) == 1
            assert (
                docker("inspect", "--format", "{{.State.Running}}", consumer).stdout.strip()
                == "true"
            )
            imported = docker(
                "exec", consumer, "python", "-c", "import cache_probe; print(cache_probe.VALUE)"
            )
            assert imported.stdout.strip() == "complete-local-wheel"
            assert cache.ready_volume(key, image, docker) == volume
            assert (
                sum(
                    docker("volume", "inspect", name, check=False).returncode == 0
                    for name in volumes
                )
                == 1
            )
    finally:
        release.set()
        docker("rm", "-f", consumer, check=False, timeout=30)


def test_killed_initializer_is_not_reused_or_stolen_by_retry(local_cache, monkeypatch):
    repo, _image, _key, docker, tracked, _volumes, _installers, _stages = local_cache
    code = """import json,sys,shutil
from pathlib import Path
from furnace.sandbox import docker_sandbox as sb
actual,original=sb._docker,sb.stage_requirements
def stage(files):
 p=original(files);shutil.copyfile(sys.argv[2],p/Path(sys.argv[2]).name);return p
def pause(*args,**kwargs):
 if args[0]=='run' and 'pip' in args:
  name=args[args.index('--name')+1]
  volume=next(value.split(':')[0] for value in args if value.endswith(':/deps'))
  staged=next(value[:-len(':/req:ro')] for value in args if value.endswith(':/req:ro'))
  print(json.dumps({'name':name,'volume':volume,'staged':staged}),flush=True)
  args=(*args[:args.index('pip')],'python','-c',"from pathlib import Path; import time; Path('/deps/partial').write_text('partial'); time.sleep(60)")
 return actual(*args,**kwargs)
sb.stage_requirements=stage;sb._docker=pause
sb._deps_volume(Path(sys.argv[1]))
"""
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            code,
            str(repo),
            str(repo.parent / "furnace_cache_probe-0.0.1-py3-none-any.whl"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    owned = None
    try:
        assert child.stdout is not None
        stdout = child.stdout
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(stdout.readline()), daemon=True).start()
        owned = json.loads(lines.get(timeout=20))
        deadline = time.monotonic() + 15
        while docker("container", "inspect", owned["name"], check=False).returncode:
            assert time.monotonic() < deadline
            time.sleep(0.1)
        child.kill()
        child.wait(timeout=10)
        monkeypatch.setattr(sb, "_docker", tracked)
        selected = sb._deps_volume(repo)
        assert selected != owned["volume"]
        assert (
            docker("inspect", "--format", "{{.State.Running}}", owned["name"]).stdout.strip()
            == "true"
        )
        result = sb.run_in_sandbox(
            repo, ["python", "-c", "import cache_probe; print(cache_probe.VALUE)"], timeout_s=15
        )
        assert result.ok and result.stdout.strip() == "complete-local-wheel"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        if owned:
            docker("rm", "-f", owned["name"], check=False, timeout=30)
            docker("volume", "rm", owned["volume"], check=False, timeout=30)
            shutil.rmtree(owned["staged"], ignore_errors=True)
        if child.stdout:
            child.stdout.close()
        if child.stderr:
            child.stderr.close()
