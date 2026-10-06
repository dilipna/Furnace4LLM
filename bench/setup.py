"""FurnaceBench setup: fetch held-out repos at their pinned commits, check the lab image
and the cached models. Idempotent; prints what it did and what is missing.

  uv run poe bench-setup
"""

from __future__ import annotations

import subprocess
import sys

import yaml
from common import EXTERNAL, GROUND_TRUTH, ROOT

IMAGE = "vllm/vllm-openai:latest"
MODELS = ["Qwen/Qwen2.5-0.5B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct-AWQ"]


def git(*args: str, cwd=None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=300)  # noqa: S603, S607


def fetch_external() -> bool:
    ok = True
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    for gt in sorted(GROUND_TRUTH.glob("*.yaml")):
        spec = yaml.safe_load(gt.read_text(encoding="utf-8"))
        dest = EXTERNAL / spec["app"]
        if not dest.exists():
            dest.mkdir()
            git("init", "-q", cwd=dest)
            git("remote", "add", "origin", spec["repo"], cwd=dest)
            r = git("fetch", "-q", "--depth", "1", "origin", spec["commit"], cwd=dest)
            if r.returncode != 0:
                print(f"FAIL {spec['app']}: {r.stderr.strip()}")
                ok = False
                continue
            git("checkout", "-q", "FETCH_HEAD", cwd=dest)
        head = git("rev-parse", "HEAD", cwd=dest).stdout.strip()
        dirty = git("status", "--porcelain", cwd=dest).stdout.strip()
        status = "ok" if head == spec["commit"] and not dirty else "MISMATCH"
        ok &= status == "ok"
        print(f"{status:8s} {spec['app']} @ {head[:12]} (pinned {spec['commit'][:12]})")
    return ok


def check_lab() -> bool:
    r = subprocess.run(  # noqa: S603
        ["docker", "image", "inspect", IMAGE, "--format", "{{index .RepoDigests 0}}"],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    print(f"{'ok' if r.returncode == 0 else 'MISSING':8s} {IMAGE} {r.stdout.strip()}")
    from pathlib import Path

    hub = Path.home() / ".cache" / "huggingface" / "hub"
    ok = r.returncode == 0
    for m in MODELS:
        present = (hub / f"models--{m.replace('/', '--')}").exists()
        ok &= present
        print(f"{'ok' if present else 'MISSING':8s} {m} in {hub}")
    return ok


if __name__ == "__main__":
    good = fetch_external() & check_lab()
    sys.exit(0 if good else 1)
