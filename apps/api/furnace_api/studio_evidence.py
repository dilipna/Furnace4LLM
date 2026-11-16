"""Versioned identity and presentation of local fixture evidence; no model claims."""

from __future__ import annotations

import hashlib
import json
from typing import Any

PROTOCOL = "framework-v2"


def case_input(case: dict[str, Any]) -> dict[str, Any]:
    return {key: case.get(key) for key in ("name", "input", "expected_behavior", "expected_output")}


def configuration_identity(project: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "project_id": project["id"],
                "contract": project["contract"],
                "plan": project["plan"],
                "cases": [case_input(case) for case in project["cases"]],
                "protocol": PROTOCOL,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def project_view(project: dict[str, Any]) -> dict[str, Any]:
    identity = configuration_identity(project)
    evaluation = project.get("evaluation")
    current = bool(
        evaluation
        and evaluation.get("project_id") == project["id"]
        and evaluation.get("configuration_sha256") == identity
        and evaluation.get("protocol") == PROTOCOL
        and evaluation.get("evidence") == "framework_fixture"
        and evaluation.get("model_execution") is False
    )
    cases = []
    for case in project["cases"]:
        value = dict(case)
        if not current and value.get("status", "not_run") != "not_run":
            value["recorded_status"] = value["status"]
            value["status"] = "not_run"
        cases.append(value)
    return {
        **project,
        "revision": project.get("revision", 0),
        "cases": cases,
        "configuration_sha256": identity,
        "evaluation_verification": "current_framework_evidence"
        if current
        else "unbound_or_stale"
        if evaluation
        else "no_current_evidence",
    }


def provenance(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": project["id"],
        "project_name": project["name"],
        "project_revision": project["revision"],
        "run_id": (project.get("evaluation") or {}).get("run_id"),
        "recorded_at": (project.get("evaluation") or {}).get("at"),
        "attempt_status": (project.get("evaluation") or {}).get("status", "not_run"),
        "runtime_state_is_snapshot": True,
        "configuration_sha256": project["configuration_sha256"],
        "verification_status": project["evaluation_verification"],
        "protocol": PROTOCOL,
        "execution_kind": "newly_executed_deterministic_fixture"
        if project["evaluation_verification"] == "current_framework_evidence"
        else "recorded_unbound_evidence"
        if project.get("evaluation")
        else "not_run",
        "model_inference": False,
        "historical_measurements": False,
        "simulated_measurements": False,
        "comparison": "Actual fixture output versus the saved expected string. No base/head model change is compared.",
        "baseline": "Author-supplied expected output; not a measured model baseline.",
        "timing": "Worker request round trip including Docker control; not model latency.",
        "limits": "No model quality, GPU performance or research-architecture compatibility established. Legacy/unbound records do not verify this configuration.",
    }
