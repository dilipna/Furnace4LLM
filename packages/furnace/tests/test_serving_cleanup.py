"""Failed Docker inspection cannot establish that an owned resource is absent."""

import os
import subprocess
import sys
import threading
import time

import pytest
from furnace.runtime import serving
from furnace.runtime.serving import ServingFault, Supervisor

PYTHON = getattr(sys, "_base_executable", sys.executable)


@pytest.mark.parametrize("kind", ["container", "network"])
def test_unavailable_inspection_is_not_successful_cleanup(tmp_path, monkeypatch, kind):
    supervisor = Supervisor(tmp_path, lambda: {})
    monkeypatch.setattr(
        supervisor,
        "_docker",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 1, "", "Cannot connect to daemon"
        ),
    )
    with pytest.raises(ServingFault):
        supervisor._remove_owned(kind, "owned-resource", "a" * 32)


@pytest.mark.parametrize("kind", ["container", "network", "object"])
def test_missing_resource_is_confirmed_absent(tmp_path, monkeypatch, kind):
    supervisor = Supervisor(tmp_path, lambda: {})
    monkeypatch.setattr(
        supervisor,
        "_docker",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 1, "", f"Error: No such {kind}: test"
        ),
    )
    supervisor._remove_owned("container" if kind == "object" else kind, "test", "a" * 32)


def test_cancelling_cli_reaps_the_actual_child(tmp_path, monkeypatch):
    processes, errors = [], []
    original = subprocess.Popen

    def capture(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(serving.subprocess, "Popen", capture)
    cancel = threading.Event()
    started = tmp_path / "started"
    command = [
        PYTHON,
        "-c",
        "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('started'); time.sleep(60)",
        str(started),
    ]

    def run():
        try:
            serving._run_cancellable(command, os.environ.copy(), 30, cancel)
        except ServingFault as exc:
            errors.append(exc.code)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert started.read_text() == "started"
    finally:
        cancel.set()
        thread.join(timeout=5)
    assert not thread.is_alive() and errors == ["preparation_cancelled"]
    assert len(processes) == 1 and processes[0].poll() is not None


def test_cli_timeout_reaps_the_actual_child(monkeypatch):
    processes = []
    original = subprocess.Popen

    def capture(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(serving.subprocess, "Popen", capture)
    with pytest.raises(ServingFault, match="docker_timeout"):
        serving._run_cancellable(
            [PYTHON, "-c", "import time; time.sleep(60)"],
            os.environ.copy(),
            0.1,
            threading.Event(),
        )
    assert len(processes) == 1 and processes[0].poll() is not None
