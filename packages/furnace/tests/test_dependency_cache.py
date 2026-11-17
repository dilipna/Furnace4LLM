"""Cache publication orchestration; real-Docker coverage is in the integration tests."""

import json
import shutil
import subprocess
import threading
from itertools import pairwise

import pytest
from furnace.sandbox import dependency_cache as cache
from furnace.sandbox import docker_sandbox as sb

IMAGE_ID = "sha256:" + "a" * 64


class Docker:
    def __init__(self, failures=()):
        self.volumes, self.containers = {}, {}
        self.calls, self.installs = [], 0
        self.failures = list(failures)
        self.guard = threading.RLock()
        self.image = IMAGE_ID

    def __call__(self, *args, **kwargs):
        with self.guard:
            self.calls.append(args)

            def result(code=0, out="", err=""):
                return subprocess.CompletedProcess(args, code, out, err)

            if args[:2] == ("image", "inspect"):
                return result(out=self.image)
            if args[:2] == ("volume", "inspect"):
                return result(0 if args[2] in self.volumes else 1)
            if args[:2] == ("volume", "create"):
                self.volumes[args[-1]] = {"complete": False, "marker": False}
                return result(out=args[-1])
            if args[:2] == ("volume", "rm"):
                assert "-f" not in args, "Never force-remove a dependency volume"
                self.volumes.pop(args[-1], None)
                return result()
            if args[:2] == ("container", "inspect"):
                return (
                    result(out=json.dumps(self.containers[args[2]]))
                    if args[2] in self.containers
                    else result(1)
                )
            if args[0] == "create":
                name = args[args.index("--name") + 1]
                if name in self.containers:
                    return result(1)
                labels = dict(
                    value.split("=", 1) for flag, value in pairwise(args) if flag == "--label"
                )
                volume = next(
                    value.split(":")[0]
                    for flag, value in pairwise(args)
                    if flag == "-v" and ":/deps" in value
                )
                self.containers[name] = {
                    "Image": self.image,
                    "Config": {"Labels": labels},
                    "Mounts": [
                        {"Type": "volume", "Name": volume, "Destination": "/deps", "RW": False}
                    ],
                }
                return result(out="published-id")
            if args[0] == "rm":
                self.containers.pop(args[-1], None)
                return result()
            if args[0] == "run":
                volume = next(
                    value.split(":")[0]
                    for flag, value in pairwise(args)
                    if flag == "-v" and ":/deps" in value
                )
                state = self.volumes[volume]
                if "pip" in args:
                    self.installs += 1
                    if "--name" in args:
                        self.containers[args[args.index("--name") + 1]] = {"installer": True}
                    failure = self.failures.pop(0) if self.failures else None
                    if failure == "timeout":
                        raise subprocess.TimeoutExpired("pip", kwargs.get("timeout", 900))
                    if failure == "exception":
                        raise OSError("controlled CLI failure")
                    if failure == "exit":
                        return result(1, err="controlled install error")
                    state["complete"] = True
                    return result()
                code = args[args.index("-c") + 1]
                if "write_text" in code:
                    state["marker"] = state["complete"]
                    return result()
                return result(0 if state["marker"] and state["complete"] else 1)
            raise AssertionError(args)


@pytest.mark.parametrize("failure", ["timeout", "exception", "exit"])
def test_interrupted_or_failed_install_retries_real_install_not_partial_volume(
    tmp_path, monkeypatch, failure
):
    (tmp_path / "requirements.txt").write_text("example==1.0\n")
    docker, staged = Docker([failure]), []
    original = sb.stage_requirements

    def stage(files):
        path = original(files)
        staged.append(path)
        return path

    monkeypatch.setattr(sb, "_docker", docker)
    monkeypatch.setattr(sb, "stage_requirements", stage)
    try:
        with pytest.raises((subprocess.TimeoutExpired, OSError, sb.SandboxError)):
            sb._deps_volume(tmp_path)
        volume = sb._deps_volume(tmp_path)
        assert docker.installs == 2, "Retry reused an incomplete dependency volume"
        assert volume and docker.volumes[volume]["complete"]
        assert all(not path.exists() for path in staged)
        assert sb._deps_volume(tmp_path) == volume
        assert docker.installs == 2
    finally:
        for path in staged:
            shutil.rmtree(path, ignore_errors=True)


def test_legacy_volume_and_image_change_never_reuse_unproven_dependencies(tmp_path, monkeypatch):
    data = b"example==1.0\n"
    (tmp_path / "requirements.txt").write_bytes(data)
    docker = Docker()
    legacy = "furnace-deps-" + sb._requirements_digest({"requirements.txt": data})
    docker.volumes[legacy] = {"complete": False, "marker": False}
    monkeypatch.setattr(sb, "_docker", docker)
    first = sb._deps_volume(tmp_path)
    docker.image = "sha256:" + "b" * 64
    second = sb._deps_volume(tmp_path)
    assert first != second != legacy
    assert docker.installs == 2 and legacy in docker.volumes
    assert not docker.volumes[legacy]["complete"]


def test_bad_published_marker_is_refused_without_mutating_the_published_cache(
    tmp_path, monkeypatch
):
    (tmp_path / "requirements.txt").write_text("example==1.0\n")
    docker = Docker()
    monkeypatch.setattr(sb, "_docker", docker)
    volume = sb._deps_volume(tmp_path)
    docker.volumes[volume]["marker"] = False
    with pytest.raises(sb.SandboxError, match="incomplete"):
        sb._deps_volume(tmp_path)
    assert docker.installs == 1 and volume in docker.volumes


def test_publication_ack_timeout_preserves_candidate_and_next_reader_reuses_it(
    tmp_path, monkeypatch
):
    (tmp_path / "requirements.txt").write_text("example==1.0\n")
    docker = Docker()
    failed = False

    def ambiguous(*args, **kwargs):
        nonlocal failed
        result = docker(*args, **kwargs)
        if args[0] == "create" and not failed:
            failed = True
            raise subprocess.TimeoutExpired("publication", 30)
        return result

    monkeypatch.setattr(sb, "_docker", ambiguous)
    with pytest.raises(subprocess.TimeoutExpired):
        sb._deps_volume(tmp_path)
    assert len(docker.volumes) == 1
    volume = sb._deps_volume(tmp_path)
    assert docker.installs == 1 and volume in docker.volumes


def test_marker_timeout_removes_only_its_named_helper_and_does_not_publish(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("example==1.0\n")
    docker, helper = Docker(), None

    def failed_marker(*args, **kwargs):
        nonlocal helper
        if args[0] == "run" and "-c" in args and "write_text" in args[args.index("-c") + 1]:
            helper = args[args.index("--name") + 1]
            raise subprocess.TimeoutExpired("marker", 30)
        return docker(*args, **kwargs)

    monkeypatch.setattr(sb, "_docker", failed_marker)
    with pytest.raises(subprocess.TimeoutExpired):
        sb._deps_volume(tmp_path)
    assert helper is not None and ("rm", "-f", helper) in docker.calls
    assert not docker.volumes and not docker.containers


def test_other_initializer_winning_publication_is_kept_and_own_candidate_removed(
    tmp_path, monkeypatch
):
    files = {"requirements.txt": b"example==1.0\n"}
    (tmp_path / "requirements.txt").write_bytes(files["requirements.txt"])
    docker = Docker()
    key = cache.cache_key("requirements.txt", files, IMAGE_ID)
    other = f"furnace-deps-v2-{key}-" + "f" * 32

    def competing(*args, **kwargs):
        if args[0] == "create":
            docker.volumes[other] = {"complete": True, "marker": True}
            reference = list(args)
            for index, value in enumerate(reference):
                if value.startswith("furnace.cache.volume="):
                    reference[index] = f"furnace.cache.volume={other}"
            mount = next(i for i, value in enumerate(reference) if value.endswith(":/deps:ro"))
            reference[mount] = other + ":/deps:ro"
            docker(*reference, **kwargs)
        return docker(*args, **kwargs)

    monkeypatch.setattr(sb, "_docker", competing)
    assert sb._deps_volume(tmp_path) == other
    assert set(docker.volumes) == {other}
