"""Local-server connections and bounded evaluation.

A connection is either to a server the researcher operates (no credentials sent),
or to a server Furnace operates (managed; called with its per-launch key, which is
held in memory by the supervisor and never persisted or exported).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from furnace.runtime.endpoint import MAX_TIMEOUT_SECONDS, LocalChatEndpoint, endpoint_port
from furnace.runtime.manager import RuntimeFault, RuntimeManager
from furnace.runtime.oplog import OperationsLog
from furnace.runtime.scoring import ScoringRule, score
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from furnace_api.studio_evidence import case_input
from furnace_api.studio_model_evidence import HISTORY_LIMIT, PROTOCOL, identity, retained_runs
from furnace_api.studio_runtime import WorkspaceStore

DEFAULT_BUDGET_SECONDS = 120


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(max_length=100)
    model_id: str = Field(min_length=1, max_length=200, pattern=r"^[\w./:@+-]+$")
    declared_revision: str = Field(min_length=1, max_length=120)
    timeout_seconds: int = Field(ge=1, le=MAX_TIMEOUT_SECONDS, default=30)
    max_tokens: int = Field(ge=1, le=1024, default=256)
    evaluation_budget_seconds: int = Field(ge=5, le=1800, default=DEFAULT_BUDGET_SECONDS)

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


def suite_digest(cases: list[dict[str, Any]]) -> str:
    """Identity of the exact case inputs, expectations and scoring rules evaluated."""
    return hashlib.sha256(
        json.dumps([case_input(c) for c in cases], sort_keys=True).encode()
    ).hexdigest()


def case_status(case: dict[str, Any], result: dict[str, Any]) -> tuple[str, str, str]:
    """(status, scoring method, reason). Token-limit termination is never a pass."""
    raw = case.get("scoring")
    try:
        rule = ScoringRule.model_validate(raw) if raw else None
    except ValidationError:
        return "error", "invalid", "invalid_scoring_rule"
    method = (
        rule.method if rule else ("exact" if case.get("expected_output") is not None else "none")
    )
    if result["finish_reason"] == "length":
        return "incomplete", method, "token_limit_reached"
    outcome, reason = score(rule, result["output"], case.get("expected_output"))
    if outcome == "unscored":
        return "unscored", method, reason
    prefix = "exact" if method == "exact" else "check"
    return f"{prefix}_{outcome}", method, reason


class ModelService:
    def __init__(
        self,
        store: WorkspaceStore,
        manager: RuntimeManager,
        oplog: OperationsLog | None = None,
    ):
        self.store, self.manager, self.oplog = store, manager, oplog
        self.client = LocalChatEndpoint()
        # Set by the managed-server service; returns the in-memory per-launch key.
        self.credentials: Callable[[str], str | None] = lambda pid: None
        self._cancel: dict[str, threading.Event] = {}
        self._guard = threading.Lock()

    def flag(self, pid: str) -> threading.Event:
        with self._guard:
            return self._cancel.setdefault(pid, threading.Event())

    def log(self, pid: str, kind: str, **fields: Any) -> None:
        if self.oplog is not None:
            self.oplog.append(pid, kind, **fields)

    def key_for(self, pid: str, config: dict[str, Any]) -> str | None:
        if not config.get("managed"):
            return None
        key = self.credentials(pid)
        if key is None:
            raise RuntimeFault("managed_server_not_running")
        return key

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
                "server_managed_by_furnace": bool(
                    (project.get("model_connection") or {}).get("managed")
                ),
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
                "Managed server connection recorded; no inference attempted"
                if config.get("managed")
                else "Local endpoint settings saved; no connection or inference attempted",
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
                self.client.check(config, api_key=self.key_for(pid, config))
                if self.flag(pid).is_set():
                    raise RuntimeFault("endpoint_disconnected")
            except RuntimeFault as exc:
                self.state(pid, "failed", exc.code)
                self.log(pid, "connection_failed", reason=exc.code)
                raise
            self.log(
                pid, "connected", model_id=config["model_id"], managed=bool(config.get("managed"))
            )
            return self.state(
                pid,
                "connected",
                "Furnace-operated server is ready; weights were SHA-256 verified before launch."
                if config.get("managed")
                else "Local server advertises this model ID. No inference or weight identity is verified.",
            )

    def disconnect(self, pid: str) -> dict:
        self.store.get(pid)
        self.flag(pid).set()
        with self.manager.lock_for(pid):
            managed = bool((self.store.get(pid).get("model_connection") or {}).get("managed"))
            return self.state(
                pid,
                "disconnected",
                "Furnace disconnected; stop the managed server separately"
                if managed
                else "Furnace disconnected; the external model server was not stopped",
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
                result = self.client.predict(
                    config, value, config["timeout_seconds"], api_key=self.key_for(pid, config)
                )
                if self.flag(pid).is_set():
                    raise RuntimeFault("endpoint_disconnected")
            except RuntimeFault as exc:
                self.state(pid, "failed", exc.code)
                self.log(pid, "request_failed", reason=exc.code, source="ad_hoc")
                raise
            self.log(
                pid,
                "request",
                request_id=result["request_id"],
                duration_ms=result["duration_ms"],
                finish_reason=result["finish_reason"],
                usage=result["usage"],
                source="ad_hoc",
            )
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
            key = self.key_for(pid, config)
            budget = config.get("evaluation_budget_seconds", 30)
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
                "suite_sha256": suite_digest(project["cases"]),
                "sampling": {"temperature": 0, "max_tokens": config["max_tokens"]},
                "budget_seconds": budget,
                "server": config.get("server"),
                "launch_id": config.get("launch_id"),
            }
            if config.get("managed"):
                run["weights_verified_before_launch"] = True
            self.save_run(pid, run, "Local endpoint evaluation started")
            self.log(pid, "evaluation_started", run_id=run["run_id"], cases=run["case_count"])
            began = time.monotonic()
            deadline = began + budget
            for index, item in enumerate(project["cases"]):
                case = case_input(item)
                try:
                    if self.flag(pid).is_set() or time.monotonic() >= deadline:
                        raise RuntimeFault("endpoint_evaluation_cancelled_or_budget_exhausted")
                    result = self.client.predict(
                        config,
                        case["input"],
                        min(config["timeout_seconds"], max(0.001, deadline - time.monotonic())),
                        api_key=key,
                    )
                    if self.flag(pid).is_set():
                        raise RuntimeFault("endpoint_evaluation_cancelled_or_budget_exhausted")
                    status, method, reason = case_status(case, result)
                    run["results"].append(
                        {
                            "case_index": index,
                            "status": status,
                            "scoring_method": method,
                            "reason": reason,
                            "request_id": result["request_id"],
                            "duration_ms": result["duration_ms"],
                            "finish_reason": result["finish_reason"],
                            "usage": result["usage"],
                            "server_timings": result["server_timings"],
                            "output_sha256": hashlib.sha256(result["output"].encode()).hexdigest(),
                        }
                    )
                    self.log(
                        pid,
                        "request",
                        run_id=run["run_id"],
                        request_id=result["request_id"],
                        duration_ms=result["duration_ms"],
                        status=status,
                        usage=result["usage"],
                        source="evaluation",
                    )
                    self.save_run(pid, run, f"Local endpoint case {index + 1} recorded: {status}")
                except RuntimeFault as exc:
                    run["status"] = "interrupted"
                    run["results"].append(
                        {"case_index": index, "status": "error", "reason": exc.code}
                    )
                    self.state(pid, "failed", exc.code)
                    self.log(pid, "request_failed", run_id=run["run_id"], reason=exc.code)
                    break
            if run["status"] == "running":
                run["status"] = "completed"
            run["elapsed_seconds"] = round(time.monotonic() - began, 2)
            self.log(
                pid,
                "evaluation_ended",
                run_id=run["run_id"],
                status=run["status"],
                elapsed_seconds=run["elapsed_seconds"],
            )
            return self.save_run(
                pid,
                run,
                "Local endpoint evaluation ended; rule checks are not human quality judgements",
            )

    def recover(self) -> None:
        for listed in self.store.all():
            pid = listed["id"]
            # Stop an in-flight batch after its bounded call, then read under the lock:
            # a copy read before waiting could overwrite the batch's final record.
            self.flag(pid).set()
            with self.manager.lock_for(pid):
                project = self.store.get(pid)
                run = project.get("model_evaluation")
                if run and run.get("status") == "running":
                    self.save_run(
                        pid,
                        {**run, "status": "interrupted"},
                        "Interrupted endpoint evaluation retained; reconnect and retry explicitly",
                    )
                if project.get("model_connection"):
                    self.disconnect(pid)
