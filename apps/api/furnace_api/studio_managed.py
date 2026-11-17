"""Furnace-operated local model servers for Studio projects.

Per project: choose a pinned recipe, prepare it (pull pinned images, download and
verify weights), start it in an isolated container, wait for real readiness, then
connect the endpoint evaluation path to it with an in-memory per-launch key.
Every phase is persisted so a restart can tell an interrupted launch from a
stopped one; Docker-owned containers left by a crash are removed on the next start.
"""

from __future__ import annotations

import contextlib
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from furnace.runtime.adapter import LaunchSettings, LlamaCppAdapter
from furnace.runtime.artifacts import ArtifactError, ArtifactStore
from furnace.runtime.catalog import (
    MODELS,
    SUITES,
    CatalogError,
    manifest_digest,
    public_catalog,
    suite_cases,
    suite_digest,
)
from furnace.runtime.manager import RuntimeFault, RuntimeManager
from furnace.runtime.oplog import OperationsLog
from furnace.runtime.serving import ServingFault, Supervisor
from pydantic import BaseModel, ConfigDict, Field, field_validator

from furnace_api.studio_model import ModelService
from furnace_api.studio_runtime import WorkspaceStore

ACTIVE = {"starting", "loading", "ready"}


class ManagedSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(max_length=100)
    accelerator: Literal["cpu", "nvidia"] = "cpu"
    context_tokens: int = Field(ge=512, le=8192, default=4096)
    threads: int = Field(ge=1, le=16, default=4)
    memory_mb: int = Field(ge=512, le=16384, default=2048)
    cpus: float = Field(ge=0.5, le=16, default=4)
    max_output_tokens: int = Field(ge=16, le=1024, default=512)
    request_timeout_seconds: int = Field(ge=1, le=120, default=60)
    max_tokens: int = Field(ge=1, le=1024, default=256)
    evaluation_budget_seconds: int = Field(ge=10, le=1800, default=600)

    @field_validator("model")
    @classmethod
    def known_model(cls, value: str) -> str:
        if value not in MODELS:
            raise ValueError("choose a reviewed model recipe")
        return value

    def settings(self) -> LaunchSettings:
        return LaunchSettings(
            accelerator=self.accelerator,
            context_tokens=self.context_tokens,
            threads=self.threads,
            memory_mb=self.memory_mb,
            cpus=self.cpus,
            max_output_tokens=max(self.max_output_tokens, self.max_tokens),
        )


class ManagedConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: Literal[True]


def now() -> str:
    return datetime.now(UTC).isoformat()


class ManagedService:
    def __init__(
        self,
        store: WorkspaceStore,
        manager: RuntimeManager,
        model: ModelService,
        workspace: Path,
        artifacts: Path,
        oplog: OperationsLog,
    ):
        self.store, self.manager, self.model, self.oplog = store, manager, model, oplog
        self.supervisor = Supervisor(workspace, manager.docker_environment)
        self.artifacts = ArtifactStore(artifacts)
        model.credentials = self.supervisor.api_key
        self.jobs: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    # -- helpers ---------------------------------------------------------------------
    def lock(self, pid: str) -> threading.RLock:
        self.manager.lock_for(pid)  # validates the identifier
        with self._guard:
            return self._locks.setdefault(pid, threading.RLock())

    def _save(self, pid: str, event: str, **changes: Any) -> dict[str, Any]:
        current = dict(self.store.get(pid).get("managed_server") or {})
        current.update(changes, updated_at=now())
        return self.store.change(pid, "managed_server", current, event)

    def _selection(self, project: dict[str, Any]) -> ManagedSelection:
        saved = (project.get("managed_server") or {}).get("selection")
        if not saved:
            raise RuntimeFault("choose_a_managed_model_first")
        return ManagedSelection.model_validate(saved)

    @staticmethod
    def _manifest(selection: ManagedSelection) -> tuple[dict[str, Any], str]:
        value = LlamaCppAdapter.for_model(selection.model).manifest(selection.settings())
        return value, manifest_digest(value)

    def catalog(self) -> dict[str, Any]:
        value = public_catalog()
        for item in value["models"]:
            recipe = MODELS[item["id"]]
            item["local"] = self.artifacts.status(recipe.weights)
            item["images_present"] = {
                acc: self.supervisor.image_present(image)
                for acc, image in LlamaCppAdapter(recipe).engine.images.items()
            }
        value["docker"] = self.supervisor.daemon()
        return value

    # -- selection and preparation ---------------------------------------------------
    def configure(self, pid: str, selection: ManagedSelection) -> dict[str, Any]:
        with self.lock(pid):
            project = self.store.get(pid)
            if (project.get("managed_server") or {}).get("status") in ACTIVE:
                raise RuntimeFault("stop_managed_server_first")
            if pid in self.jobs:
                raise RuntimeFault("preparation_in_progress")
            value, digest = self._manifest(selection)
            return self.store.change(
                pid,
                "managed_server",
                {
                    "selection": selection.model_dump(),
                    "status": "configured",
                    "reason": "Selection saved; nothing downloaded or started",
                    "manifest": value,
                    "manifest_sha256": digest,
                    "updated_at": now(),
                },
                f"Managed model selected: {selection.model} on {selection.accelerator}",
            )

    def prepare(self, pid: str) -> dict[str, Any]:
        with self.lock(pid):
            project = self.store.get(pid)
            selection = self._selection(project)
            if (project.get("managed_server") or {}).get("status") in ACTIVE:
                raise RuntimeFault("stop_managed_server_first")
            with self._guard:
                if pid in self.jobs:
                    return self.view(pid)
                cancel = threading.Event()
                job: dict[str, Any] = {"cancel": cancel, "progress": {"phase": "queued"}}
                self.jobs[pid] = job
            self._save(pid, "Preparation started", status="preparing", reason="Preparing")
            thread = threading.Thread(target=self._prepare, args=(pid, selection, job), daemon=True)
            job["thread"] = thread
            thread.start()
            return self.view(pid)

    def _prepare(self, pid: str, selection: ManagedSelection, job: dict[str, Any]) -> None:
        adapter = LlamaCppAdapter.for_model(selection.model)
        began = time.monotonic()
        cancel: threading.Event = job["cancel"]
        try:
            for image in adapter.images(selection.settings()):
                job["progress"] = {"phase": "image", "image": image}
                self.supervisor.pull(image)
                if cancel.is_set():
                    raise ArtifactError("preparation_cancelled")
            for artifact in adapter.artifacts():

                def progress(done: int, total: int, name: str = artifact.filename) -> None:
                    job["progress"] = {
                        "phase": "weights",
                        "file": name,
                        "bytes": done,
                        "size": total,
                    }

                job["progress"] = {"phase": "weights", "file": artifact.filename, "bytes": 0}
                self.artifacts.fetch(artifact, progress=progress, cancel=cancel)
            elapsed = round(time.monotonic() - began, 1)
            self._save(
                pid,
                f"Managed model prepared and verified in {elapsed} s",
                status="prepared",
                reason="Images pulled by digest; weights SHA-256 verified",
                prepared_at=now(),
            )
            self.oplog.append(pid, "prepared", model=selection.model, seconds=elapsed)
        except (ArtifactError, ServingFault, RuntimeFault, OSError) as exc:
            code = getattr(exc, "code", "preparation_io_error")
            self._save(pid, f"Preparation stopped: {code}", status="failed", reason=code)
            self.oplog.append(pid, "prepare_failed", reason=code)
        finally:
            with self._guard:
                self.jobs.pop(pid, None)

    def cancel(self, pid: str) -> dict[str, Any]:
        job = self.jobs.get(pid)
        if job is not None:
            job["cancel"].set()
        return self.view(pid)

    # -- lifecycle -------------------------------------------------------------------
    def start(self, pid: str) -> dict[str, Any]:
        with self.lock(pid):
            project = self.store.get(pid)
            selection = self._selection(project)
            saved = project.get("managed_server") or {}
            if saved.get("status") in ACTIVE:
                raise RuntimeFault("managed_server_already_running")
            if pid in self.jobs:
                raise RuntimeFault("preparation_in_progress")
            adapter = LlamaCppAdapter.for_model(selection.model)
            settings = selection.settings()
            value, digest = self._manifest(selection)
            began = time.monotonic()
            try:
                files = {a.sha256: self.artifacts.verify(a) for a in adapter.artifacts()}
            except ArtifactError as exc:
                self._save(pid, f"Start refused: {exc.code}", status="failed", reason=exc.code)
                raise RuntimeFault(
                    "prepare_managed_model_first" if exc.code == "artifact_missing" else exc.code
                ) from None
            spec = adapter.launch(files, settings)
            self._save(
                pid,
                "Managed server starting; weights SHA-256 verified before launch",
                status="starting",
                reason="Starting isolated server container",
                manifest=value,
                manifest_sha256=digest,
            )
            try:
                launch = self.supervisor.start(pid, spec, {"furnace.managed.manifest": digest[:32]})
                self._save(
                    pid,
                    f"Managed server container started (launch {launch['launch_id'][:8]})",
                    status="loading",
                    reason="Loading model weights",
                    launch=launch,
                )
                ready = self.supervisor.wait_ready(pid, spec)
            except ServingFault as exc:
                with contextlib.suppress(ServingFault):
                    self.supervisor.stop(pid)
                self._save(
                    pid,
                    f"Managed server failed to start: {exc.code}",
                    status="failed",
                    reason=exc.code,
                    failure=exc.detail,
                )
                self.oplog.append(pid, "start_failed", reason=exc.code)
                raise RuntimeFault(exc.code) from None
            seconds = round(time.monotonic() - began, 2)
            self._save(
                pid,
                f"Managed server ready in {seconds} s",
                status="ready",
                reason="Server reports healthy; connected for evaluation",
                ready_at=now(),
                start_seconds=seconds,
                load_seconds=ready["load_seconds"],
            )
            recipe = MODELS[selection.model]
            self.oplog.append(
                pid,
                "ready",
                launch_id=launch["launch_id"],
                manifest_sha256=digest,
                start_seconds=seconds,
                accelerator=selection.accelerator,
            )
            config = {
                "managed": True,
                "base_url": launch["base_url"],
                "model_id": spec.model_id,
                "declared_revision": f"{recipe.repository}@{recipe.revision[:12]} "
                f"weights sha256:{recipe.weights.sha256[:16]}",
                "timeout_seconds": selection.request_timeout_seconds,
                "max_tokens": selection.max_tokens,
                "evaluation_budget_seconds": selection.evaluation_budget_seconds,
                "launch_id": launch["launch_id"],
                "server": {
                    "manifest_sha256": digest,
                    "model": recipe.id,
                    "engine": recipe.engine,
                    "accelerator": selection.accelerator,
                    "image": spec.image,
                    "weights_sha256": recipe.weights.sha256,
                },
            }
            self.model.configure(pid, config, own_port=None)
            self.model.connect(pid, True)
            return self.view(pid)

    def stop(self, pid: str, reason: str = "Managed server stopped") -> dict[str, Any]:
        self.model.flag(pid).set()  # stop issuing requests before waiting for any lock
        with self.lock(pid):
            project = self.store.get(pid)
            if (project.get("model_connection") or {}).get("managed"):
                self.model.disconnect(pid)
            try:
                self.supervisor.stop(pid)
            except ServingFault as exc:
                self._save(
                    pid, "Managed server cleanup unconfirmed", status="unknown", reason=exc.code
                )
                raise RuntimeFault(exc.code) from None
            if (project.get("managed_server") or {}).get("status") is None:
                return self.view(pid)
            self._save(pid, reason, status="stopped", reason=reason, stopped_at=now())
            self.oplog.append(pid, "stopped", reason=reason)
            return self.view(pid)

    def refresh(self, pid: str) -> dict[str, Any]:
        """Turn a dead container into a recorded failure; never restarts on its own."""
        with self.lock(pid):
            saved = self.store.get(pid).get("managed_server") or {}
            if saved.get("status") not in {"ready", "loading"}:
                return self.view(pid)
            try:
                state = self.supervisor.container_state(pid)
            except ServingFault as exc:
                state = {"running": False, "failure": exc.code}
            if state["running"]:
                return self.view(pid)
            failure = state.get("failure") or "server_exited"
            self.model.flag(pid).set()
            self._save(
                pid, f"Managed server stopped unexpectedly: {failure}", status="failed",
                reason=failure, failure=state,
            )  # fmt: skip
            self.oplog.append(
                pid, "server_failed", reason=failure, exit_code=state.get("exit_code")
            )
            with contextlib.suppress(RuntimeFault):
                self.model.state(pid, "failed", failure)
            with contextlib.suppress(ServingFault):
                self.supervisor.stop(pid)
            return self.view(pid)

    def view(self, pid: str) -> dict[str, Any]:
        project = self.store.get(pid)
        saved: dict[str, Any] = project.get("managed_server") or {"status": "not_configured"}
        job = self.jobs.get(pid)
        selection = saved.get("selection")
        local = None
        if selection and selection.get("model") in MODELS:
            local = self.artifacts.status(MODELS[selection["model"]].weights)
        return {
            **saved,
            "preparation": job["progress"] if job else None,
            "weights": local,
            "api_key_persisted": False,
        }

    def observe(self, pid: str, tail: int = 120) -> dict[str, Any]:
        view = self.refresh(pid)
        running = view.get("status") == "ready"
        return {
            "managed_server": view,
            "container": self.supervisor.container_state(pid) if running else None,
            "resources": self.supervisor.stats(pid) if running else {},
            "metrics": self.supervisor.metrics(pid) if running else {},
            "logs": self.supervisor.logs(pid, tail) if running else "",
            "operations": self.oplog.read(pid, 50),
        }

    def load_suite(self, pid: str, runtime_update: Any) -> dict[str, Any]:
        project = self.store.get(pid)
        selection = self._selection(project)
        suite_id = MODELS[selection.model].suite
        try:
            cases = [{**case, "status": "not_run"} for case in suite_cases(suite_id)]
        except CatalogError:
            raise RuntimeFault("reference_suite_digest_mismatch") from None
        return runtime_update(
            pid,
            "cases",
            cases,
            f"Reference suite {suite_id} loaded (sha256 {suite_digest(suite_id)[:16]}); "
            f"{SUITES[suite_id].description}",
        )

    # -- application lifecycle -------------------------------------------------------
    def recover(self) -> list[str]:
        removed = self.supervisor.recover() if self._docker_reachable() else []
        for project in self.store.all():
            saved = project.get("managed_server") or {}
            if saved.get("status") in ACTIVE | {"preparing"}:
                self._save(
                    project["id"],
                    "Previous Studio session ended; managed server removed, start explicitly",
                    status="interrupted",
                    reason="Studio restarted; containers from the previous session were removed"
                    if removed
                    else "Studio restarted; start explicitly",
                )
        if removed:
            self.oplog.append(None, "orphans_removed", names=removed)
        return removed

    def _docker_reachable(self) -> bool:
        try:
            self.manager.docker_environment()
        except RuntimeFault:
            return False
        return self.supervisor.daemon()["status"] == "ready"

    def close(self) -> None:
        for job in list(self.jobs.values()):
            job["cancel"].set()
        for job in list(self.jobs.values()):
            thread = job.get("thread")
            if thread is not None:
                thread.join(timeout=10)
        for project in self.store.all():
            if (project.get("managed_server") or {}).get("status") in ACTIVE:
                with contextlib.suppress(RuntimeFault):
                    self.stop(project["id"], "Managed server stopped with the application")
