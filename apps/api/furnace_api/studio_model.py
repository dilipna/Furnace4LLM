"""Explicit local-server connections and bounded evaluation; never owns the server."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from furnace.runtime.endpoint import LocalChatEndpoint, endpoint_port
from furnace.runtime.manager import RuntimeFault, RuntimeManager
from pydantic import BaseModel, ConfigDict, Field, field_validator

from furnace_api.studio_evidence import case_input
from furnace_api.studio_model_evidence import HISTORY_LIMIT, PROTOCOL, identity, retained_runs
from furnace_api.studio_runtime import WorkspaceStore


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(max_length=100)
    model_id: str = Field(min_length=1, max_length=200, pattern=r"^[\w./:@+-]+$")
    declared_revision: str = Field(min_length=1, max_length=120)
    timeout_seconds: int = Field(ge=1, le=10, default=5)
    max_tokens: int = Field(ge=1, le=256, default=128)

    @field_validator("base_url")
    @classmethod
    def local_url(cls, value: str) -> str:
        try:
            endpoint_port(value)
        except RuntimeFault as exc:
            raise ValueError(exc.code) from None
        return value

    @field_validator("declared_revision")
    @classmethod
    def nonempty_revision(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Declare the code/checkpoint or server revision")
        return value.strip()


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool = Field(strict=True)


class ModelPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field(min_length=1, max_length=4000)


class ModelService:
    def __init__(self, store: WorkspaceStore, manager: RuntimeManager):
        self.store, self.manager = store, manager
        self.client = LocalChatEndpoint()
        self._cancel: dict[str, threading.Event] = {}
        self._guard = threading.Lock()

    def flag(self, pid: str) -> threading.Event:
        with self._guard:
            return self._cancel.setdefault(pid, threading.Event())

    def state(self, pid: str, status: str, reason: str) -> dict:
        project = self.store.get(pid)
        return self.store.change(
            pid,
            "model_connection_state",
            {
                "status": status,
                "reason": reason,
                "configuration_sha256": identity(project),
                "checked_at": datetime.now(UTC).isoformat(),
                "server_managed_by_furnace": False,
            },
            reason,
        )

    def configure(self, pid: str, config: dict, own_port: int | None) -> dict:
        self.store.get(pid)
        if endpoint_port(config["base_url"]) == own_port:
            raise RuntimeFault("studio_cannot_be_its_own_model_endpoint")
        self.flag(pid).set()
        with self.manager.lock_for(pid):
            history = retained_runs(self.store.get(pid))
            return self.store.change(
                pid,
                "model_connection",
                config,
                "Local endpoint settings saved; no connection or inference attempted",
                extra={
                    "model_connection_state": {"status": "disconnected"},
                    "model_evaluation": None,
                    "model_evaluation_history": history,
                },
            )

    def connect(self, pid: str, consent: bool) -> dict:
        self.store.get(pid)
        if not consent:
            raise RuntimeFault("explicit_local_endpoint_consent_required")
        with self.manager.lock_for(pid):
            project = self.store.get(pid)
            config = project.get("model_connection")
            if not config:
                raise RuntimeFault("configure_local_endpoint_first")
            self.flag(pid).clear()
            self.state(
                pid, "checking", "Checking the local server's advertised model; not inference"
            )
            try:
                self.client.check(config)
                if self.flag(pid).is_set():
                    raise RuntimeFault("endpoint_disconnected")
            except RuntimeFault as exc:
                self.state(pid, "failed", exc.code)
                raise
            return self.state(
                pid,
                "connected",
                "Local server advertises this model ID. No inference or weight identity is verified.",
            )

    def disconnect(self, pid: str) -> dict:
        self.store.get(pid)
        self.flag(pid).set()
        with self.manager.lock_for(pid):
            return self.state(
                pid,
                "disconnected",
                "Furnace disconnected; the external model server was not stopped",
            )

    def ready(self, pid: str) -> tuple[dict, dict]:
        project = self.store.get(pid)
        state = project.get("model_connection_state") or {}
        if (
            state.get("status") != "connected"
            or state.get("configuration_sha256") != identity(project)
            or self.flag(pid).is_set()
        ):
            raise RuntimeFault("connect_current_model_configuration_first")
        return project, project["model_connection"]

    def predict(self, pid: str, value: str) -> dict:
        self.store.get(pid)
        with self.manager.lock_for(pid):
            project, config = self.ready(pid)
            try:
                result = self.client.predict(config, value, config["timeout_seconds"])
                if self.flag(pid).is_set():
                    raise RuntimeFault("endpoint_disconnected")
            except RuntimeFault as exc:
                self.state(pid, "failed", exc.code)
                raise
            saved = self.store.change(
                pid,
                "model_connection_state",
                project["model_connection_state"],
                f"Local endpoint request {result['request_id']} received; prompt/output not logged",
            )
            return {
                **result,
                "project_id": pid,
                "configuration_sha256": identity(project),
                "project_revision": saved["revision"],
            }

    def save_run(self, pid: str, run: dict, event: str) -> dict:
        # Callers hold the project lock. Current result and bounded history commit together.
        history = [r for r in retained_runs(self.store.get(pid)) if r["run_id"] != run["run_id"]]
        return self.store.change(
            pid,
            "model_evaluation",
            run,
            event,
            extra={"model_evaluation_history": [*history, run][-HISTORY_LIMIT:]},
        )

    def evaluate(self, pid: str) -> dict:
        self.store.get(pid)
        with self.manager.lock_for(pid):
            project, config = self.ready(pid)
            if not project["cases"]:
                raise RuntimeFault("add_evaluation_cases_first")
            run: dict[str, Any] = {
                "run_id": uuid.uuid4().hex,
                "at": datetime.now(UTC).isoformat(),
                "project_id": pid,
                "configuration_sha256": identity(project),
                "protocol": PROTOCOL,
                "status": "running",
                "execution_kind": "local_endpoint_response",
                "model_identity_independently_verified": False,
                "results": [],
                "declared_revision": config["declared_revision"],
                "model_id": config["model_id"],
                "case_count": len(project["cases"]),
            }
            self.save_run(pid, run, "Local endpoint evaluation started")
            deadline = time.monotonic() + 30
            for index, item in enumerate(project["cases"]):
                case = case_input(item)
                try:
                    if self.flag(pid).is_set() or time.monotonic() >= deadline:
                        raise RuntimeFault("endpoint_evaluation_cancelled_or_budget_exhausted")
                    result = self.client.predict(
                        config,
                        case["input"],
                        min(config["timeout_seconds"], max(0.001, deadline - time.monotonic())),
                    )
                    if self.flag(pid).is_set():
                        raise RuntimeFault("endpoint_evaluation_cancelled_or_budget_exhausted")
                    expected = case["expected_output"]
                    # A token-limit termination is incomplete; even matching text cannot pass.
                    status = (
                        "incomplete"
                        if result["finish_reason"] == "length"
                        else "unscored"
                        if expected is None
                        else "exact_pass"
                        if result["output"] == expected
                        else "exact_fail"
                    )
                    run["results"].append(
                        {
                            "case_index": index,
                            "status": status,
                            "request_id": result["request_id"],
                            "duration_ms": result["duration_ms"],
                            "finish_reason": result["finish_reason"],
                            "output_sha256": hashlib.sha256(result["output"].encode()).hexdigest(),
                        }
                    )
                    self.save_run(
                        pid,
                        run,
                        f"Local endpoint case {index + 1} recorded: {status}",
                    )
                except RuntimeFault as exc:
                    run["status"] = "interrupted"
                    run["results"].append(
                        {"case_index": index, "status": "error", "reason": exc.code}
                    )
                    self.state(pid, "failed", exc.code)
                    break
            if run["status"] == "running":
                run["status"] = "completed"
            return self.save_run(
                pid,
                run,
                "Local endpoint evaluation ended; exact checks are not semantic quality",
            )

    def recover(self) -> None:
        for project in self.store.all():
            pid = project["id"]
            with self.manager.lock_for(pid):
                run = project.get("model_evaluation")
                if run and run.get("status") == "running":
                    self.save_run(
                        pid,
                        {**run, "status": "interrupted"},
                        "Interrupted endpoint evaluation retained; reconnect and retry explicitly",
                    )
                if project.get("model_connection"):
                    self.disconnect(pid)
