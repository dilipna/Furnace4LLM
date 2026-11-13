"""Runtime lifecycle and evidence binding for the local Studio application."""

from __future__ import annotations

import contextlib
import hashlib
import json
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from furnace.runtime.manager import RuntimeFault, RuntimeManager

ACTIVE = {"starting", "ready", "unknown", "failed"}


class WorkspaceStore(Protocol):
    def get(self, project_id: str) -> dict[str, Any]: ...
    def all(self) -> list[dict[str, Any]]: ...
    def change(
        self,
        project_id: str,
        field: str,
        value: Any,
        event: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    def delete(self, project_id: str) -> None: ...


class RuntimeService:
    def __init__(self, store: WorkspaceStore, manager: RuntimeManager):
        self.store, self.manager = store, manager
        self._cancel: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()

    def cancel_flag(self, project_id: str) -> threading.Event:
        with self._cancel_lock:
            return self._cancel.setdefault(project_id, threading.Event())

    def _runtime(self, project_id: str, status: str, reason: str, **data: Any) -> dict[str, Any]:
        runtime = {
            "status": status,
            "adapter": "framework_fixture",
            "model_execution": False,
            "reason": reason,
            **data,
        }
        return self.store.change(project_id, "runtime", runtime, reason)

    def _fail(self, project_id: str, code: str) -> None:
        try:
            self.manager.stop(project_id)
        except RuntimeFault:
            self._runtime(
                project_id, "unknown", "Worker cleanup could not be confirmed; check local Docker"
            )
        else:
            self._runtime(
                project_id, "failed", f"Framework worker failed: {code}; execution stopped"
            )

    def start(self, project_id: str) -> dict[str, Any]:
        self.store.get(project_id)
        with self.manager.lock_for(project_id):
            project = self.store.get(project_id)
            if not project["plan"]:
                raise RuntimeFault("configure_infrastructure_first")
            self.cancel_flag(project_id).clear()
            self._runtime(
                project_id, "starting", "Starting isolated infrastructure fixture, not a model"
            )
            try:
                runtime = self.manager.start(project_id)
            except RuntimeFault as exc:
                self._fail(project_id, exc.code)
                raise
            return self.store.change(
                project_id,
                "runtime",
                {**runtime, "reason": "Infrastructure fixture ready; no model is connected"},
                "Infrastructure fixture ready; no model is connected",
            )

    def stop(self, project_id: str, reason: str = "Framework worker stopped") -> dict[str, Any]:
        self.store.get(project_id)
        self.cancel_flag(project_id).set()
        with self.manager.lock_for(project_id):
            runtime = self.store.get(project_id).get("runtime")
            if isinstance(runtime, dict) and runtime.get("status") in ACTIVE:
                try:
                    self.manager.stop(project_id)
                except RuntimeFault:
                    self._runtime(
                        project_id,
                        "unknown",
                        "Worker cleanup could not be confirmed; check local Docker",
                    )
                    raise
            return self._runtime(project_id, "stopped", reason)

    def status(self, project_id: str) -> dict[str, Any]:
        self.store.get(project_id)
        with self.manager.lock_for(project_id):
            project = self.store.get(project_id)
            runtime = project.get("runtime")
            if not isinstance(runtime, dict) or runtime.get("status") not in {
                "ready",
                "starting",
                "unknown",
            }:
                return project
            try:
                info = self.manager.inspect(project_id)
                if info is None or not info["State"]["Running"]:
                    return self._runtime(
                        project_id, "failed", "Framework worker is not running; restart explicitly"
                    )
                if runtime.get("status") == "ready":
                    health = self.manager._exchange(project_id, {"operation": "health"}, timeout=3)
                    if health.get("ready") is not True:
                        raise RuntimeFault("worker_unhealthy")
                return project
            except RuntimeFault as exc:
                self._fail(project_id, exc.code)
                return self.store.get(project_id)

    def update(self, project_id: str, field: str, value: Any, message: str) -> dict[str, Any]:
        self.store.get(project_id)
        with self.manager.lock_for(project_id):
            project = self.store.get(project_id)
            runtime = project.get("runtime")
            if isinstance(runtime, dict) and runtime.get("status") in {
                "ready",
                "starting",
                "unknown",
            }:
                raise RuntimeFault("stop_worker_before_editing")
            extra: dict[str, Any] = {"evaluation": None}
            if field in {"contract", "plan"}:
                extra["cases"] = [{**case, "status": "not_run"} for case in project["cases"]]
            return self.store.change(project_id, field, value, message, extra=extra)

    def predict(self, project_id: str, value: str, operation: str) -> dict[str, Any]:
        self.store.get(project_id)
        with self.manager.lock_for(project_id):
            project = self.store.get(project_id)
            runtime = project.get("runtime")
            if not isinstance(runtime, dict) or runtime.get("status") != "ready":
                raise RuntimeFault("worker_not_ready")
            try:
                result = self.manager.predict(
                    project_id,
                    value,
                    timeout_s=min(project["plan"]["timeout_seconds"], 5),
                    operation=operation,
                )
            except RuntimeFault as exc:
                self._fail(project_id, exc.code)
                raise
            self.store.change(
                project_id,
                "runtime",
                runtime,
                f"Framework request {result['request_id']} completed in {result['duration_ms']} ms; input/output not logged",
            )
            return result

    def evaluate(self, project_id: str) -> dict[str, Any]:
        self.store.get(project_id)
        with self.manager.lock_for(project_id):
            project = self.store.get(project_id)
            runtime = project.get("runtime")
            if not isinstance(runtime, dict) or runtime.get("status") != "ready":
                raise RuntimeFault("worker_not_ready")
            if not project["cases"]:
                raise RuntimeFault("add_evaluation_cases_first")
            source = [{k: v for k, v in case.items() if k != "status"} for case in project["cases"]]
            identity = hashlib.sha256(
                json.dumps(
                    {
                        "cases": source,
                        "contract": project["contract"],
                        "plan": project["plan"],
                        "protocol": "framework-v1",
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            cases = [{**case, "status": "not_run"} for case in source]
            evaluation = {
                "status": "running",
                "evidence": "framework_fixture",
                "model_execution": False,
                "configuration_sha256": identity,
                "container_id": runtime.get("container_id"),
                "run_id": uuid.uuid4().hex,
                "at": datetime.now(UTC).isoformat(),
                "results": [],
            }
            self.store.change(
                project_id,
                "cases",
                cases,
                "Infrastructure fixture evaluation started",
                extra={"evaluation": evaluation},
            )
            deadline = time.monotonic() + 30
            for index, case in enumerate(cases):
                try:
                    if self.cancel_flag(project_id).is_set():
                        raise RuntimeFault("evaluation_cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeFault("evaluation_time_budget_exhausted")
                    result = self.manager.predict(
                        project_id,
                        case["input"],
                        timeout_s=min(project["plan"]["timeout_seconds"], 5, remaining),
                    )
                except RuntimeFault as exc:
                    case["status"] = (
                        "not_run"
                        if exc.code in {"evaluation_cancelled", "evaluation_time_budget_exhausted"}
                        else "error"
                    )
                    evaluation["results"].append(
                        {"case_index": index, "status": case["status"], "reason": exc.code}
                    )
                    evaluation["status"] = "interrupted"
                    self._fail(project_id, exc.code)
                    break
                expected = case.get("expected_output")
                matched = result["output"] == expected if expected is not None else None
                case["status"] = (
                    "unscored"
                    if matched is None
                    else ("framework_pass" if matched else "framework_fail")
                )
                evaluation["results"].append(
                    {
                        "case_index": index,
                        "status": case["status"],
                        "matched": matched,
                        "duration_ms": result["duration_ms"],
                        "request_id": result["request_id"],
                        "output_sha256": hashlib.sha256(result["output"].encode()).hexdigest(),
                    }
                )
                self.store.change(
                    project_id,
                    "cases",
                    cases,
                    f"Framework case {index + 1} recorded: {case['status']}",
                    extra={"evaluation": evaluation},
                )
            if evaluation["status"] == "running":
                evaluation["status"] = "completed"
            return self.store.change(
                project_id,
                "cases",
                cases,
                "Infrastructure fixture evaluation ended; these are not model-quality results",
                extra={"evaluation": evaluation},
            )

    def _interrupt_evaluation(self, project_id: str) -> None:
        evaluation = self.store.get(project_id).get("evaluation")
        if evaluation and evaluation.get("status") == "running":
            self.store.change(
                project_id,
                "evaluation",
                {**evaluation, "status": "interrupted"},
                "Incomplete framework evaluation interrupted; missing results are not passes",
            )

    def remove(self, project_id: str) -> None:
        self.store.get(project_id)
        with self.manager.lock_for(project_id):
            self.stop(project_id)
            self.store.delete(project_id)

    def recover(self) -> None:
        for project in self.store.all():
            self._interrupt_evaluation(project["id"])
            runtime = project.get("runtime")
            if isinstance(runtime, dict) and runtime.get("status") in ACTIVE:
                try:
                    self.stop(
                        project["id"],
                        "Interrupted worker removed after application restart; start explicitly",
                    )
                    self._runtime(
                        project["id"],
                        "interrupted",
                        "Previous application session ended; worker removed, start explicitly",
                    )
                except RuntimeFault:
                    pass  # persisted unknown state already explains unconfirmed cleanup

    def close(self) -> None:
        for project in self.store.all():
            self._interrupt_evaluation(project["id"])
            runtime = project.get("runtime")
            if isinstance(runtime, dict) and runtime.get("status") in ACTIVE:
                # Keep persisted unknown state if cleanup cannot be confirmed.
                with contextlib.suppress(RuntimeFault):
                    self.stop(project["id"], "Framework worker stopped with the application")
