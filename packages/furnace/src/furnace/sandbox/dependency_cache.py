"""Publish completed immutable dependency volumes through a Docker metadata reference.

Installers never share a writable volume. A stopped reference container is created
atomically after successful installation; readers use only its validated read-only
mount. Concurrent installers may duplicate work, but cannot expose partial contents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from pathlib import Path

Docker = Callable[..., subprocess.CompletedProcess[str]]
log = logging.getLogger(__name__)
MARKER = "/deps/.furnace-ready-v2.json"
WRITE_MARKER = f"""import json,sys
from pathlib import Path
p=Path({MARKER!r})
p.unlink(missing_ok=True)
p.write_text(json.dumps({{'protocol':2,'key':sys.argv[1],'image':sys.argv[2]}}))
"""
READ_MARKER = f"""import json,sys
from pathlib import Path
p=Path({MARKER!r})
assert not p.is_symlink() and p.is_file() and p.stat().st_size < 4096
assert json.loads(p.read_text()) == {{'protocol':2,'key':sys.argv[1],'image':sys.argv[2]}}
"""


class CacheError(Exception):
    pass


def image_identity(image: str, docker: Docker) -> str:
    value = docker("image", "inspect", image, "--format", "{{.Id}}", timeout=30).stdout.strip()
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
        raise CacheError("sandbox image identity unavailable")
    return value


def cache_key(entry: str, files: dict[str, bytes], image: str) -> str:
    digest = hashlib.sha256(b"furnace-deps-v2\0" + image.encode() + b"\0" + entry.encode() + b"\0")
    for name in sorted(files):
        digest.update(name.encode() + b"\0" + hashlib.sha256(files[name]).digest())
    return digest.hexdigest()


def marker(
    docker: Docker, volume: str, image: str, key: str, *, write: bool = False
) -> subprocess.CompletedProcess[str]:
    name = "furnace-deps-marker-" + uuid.uuid4().hex
    try:
        return docker(
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--memory",
            "128m",
            "--cpus",
            "1",
            "--pids-limit",
            "32",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-v",
            f"{volume}:/deps" + ("" if write else ":ro"),
            image,
            "python",
            "-I",
            "-S",
            "-c",
            WRITE_MARKER if write else READ_MARKER,
            key,
            image,
            timeout=30,
            check=False,
        )
    finally:
        try:
            docker("rm", "-f", name, check=False, timeout=30)
        except Exception:
            log.warning("Cache marker helper cleanup could not be confirmed: %s", name)


def ready_volume(key: str, image: str, docker: Docker) -> str | None:
    reference = docker(
        "container",
        "inspect",
        "furnace-deps-v2-ready-" + key,
        "--format",
        "{{json .}}",
        timeout=30,
        check=False,
    )
    if reference.returncode:
        return None
    volume = ""
    try:
        info = json.loads(reference.stdout)
        labels = info["Config"]["Labels"]
        volume = labels["furnace.cache.volume"]
        valid = (
            info["Image"] == image
            and labels["furnace.cache.key"] == key
            and labels["furnace.cache.protocol"] == "2"
            and re.fullmatch(r"furnace-deps-v2-" + key + r"-[a-f0-9]{32}", volume)
            and any(
                m.get("Type") == "volume"
                and m.get("Name") == volume
                and m.get("Destination") == "/deps"
                and m.get("RW") is False
                for m in info["Mounts"]
            )
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise CacheError("dependency cache reference is invalid; owner review required")
    verified = marker(docker, volume, image, key)
    if verified.returncode:
        raise CacheError("published dependency cache is incomplete; owner review required")
    return volume


def prepare(
    entry: str,
    files: dict[str, bytes],
    image: str,
    docker: Docker,
    stage: Callable[[dict[str, bytes]], Path],
    *,
    timeout: float = 900,
) -> str:
    key = cache_key(entry, files, image)
    existing = ready_volume(key, image, docker)
    if existing:
        return existing
    candidate = f"furnace-deps-v2-{key}-{uuid.uuid4().hex}"
    installer = "furnace-deps-install-" + uuid.uuid4().hex
    staged = None
    created = published = publication_attempted = False
    try:
        docker(
            "volume",
            "create",
            "--label",
            "furnace.cache.protocol=2",
            "--label",
            f"furnace.cache.key={key}",
            candidate,
        )
        created = True
        staged = stage(files)
        installed = docker(
            "run",
            "--rm",
            "--name",
            installer,
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
            f"{staged.resolve()}:/req:ro",
            "-v",
            f"{candidate}:/deps",
            image,
            "pip",
            "install",
            "--no-cache-dir",
            "--target",
            "/deps",
            "-r",
            f"/req/{entry}",
            timeout=timeout,
            check=False,
        )
        if installed.returncode:
            raise CacheError(f"dependency install failed: {installed.stderr.strip()[-800:]}")
        if marker(docker, candidate, image, key, write=True).returncode:
            raise CacheError("dependency cache completion marker could not be written")
        # This metadata container is never started. Its name publishes one completed
        # volume atomically, and its read-only mount keeps Docker's volume reference.
        publication_attempted = True
        deadline = time.monotonic() + 30
        publication = docker(
            "create",
            "--name",
            "furnace-deps-v2-ready-" + key,
            "--label",
            "furnace.cache.protocol=2",
            "--label",
            f"furnace.cache.key={key}",
            "--label",
            f"furnace.cache.volume={candidate}",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-v",
            f"{candidate}:/deps:ro",
            image,
            "true",
            timeout=30,
            check=False,
        )
        # A competing create can reserve the name before its reference becomes
        # inspectable. Confirm publication within the same bounded create budget;
        # never reuse either candidate without the existing identity/marker checks.
        selected = ready_volume(key, image, docker)
        while selected is None and time.monotonic() < deadline:
            time.sleep(0.1)
            selected = ready_volume(key, image, docker)
        if selected is None:
            raise CacheError(
                "dependency cache publication could not be confirmed: "
                f"create exited {publication.returncode}: {publication.stderr.strip()[-800:]}"
            )
        published = selected == candidate
        if not published:
            publication_attempted = (
                False  # Another immutable reference won; ours cannot replace it.
            )
        return selected
    finally:
        try:
            docker("rm", "-f", installer, check=False, timeout=30)
        except Exception:
            log.warning("Cache installer cleanup could not be confirmed: %s", installer)
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        # After an ambiguous publish failure, keep the candidate: publication may
        # have succeeded. Never remove or mutate a selected/published volume.
        if created and not published and not publication_attempted:
            try:
                removed = docker("volume", "rm", candidate, check=False, timeout=30)
                if removed.returncode:
                    log.warning("Unpublished cache candidate needs owner cleanup: %s", candidate)
            except Exception:
                log.warning(
                    "Unpublished cache candidate cleanup could not be confirmed: %s", candidate
                )
