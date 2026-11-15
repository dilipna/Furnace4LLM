"""Identity of endpoint observations, kept separate from infrastructure-fixture evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

PROTOCOL = "local-chat-v1"


def identity(project: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "project_id": project["id"],
                "contract": project["contract"],
                "plan": project["plan"],
                "cases": [
                    {
                        key: c.get(key)
                        for key in ("name", "input", "expected_behavior", "expected_output")
                    }
                    for c in project["cases"]
                ],
                "connection": project.get("model_connection"),
                "protocol": PROTOCOL,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def view(project: dict[str, Any]) -> dict[str, Any]:
    digest = identity(project)
    evaluation = project.get("model_evaluation")
    current = bool(
        evaluation
        and evaluation.get("project_id") == project["id"]
        and evaluation.get("configuration_sha256") == digest
        and evaluation.get("protocol") == PROTOCOL
        and evaluation.get("execution_kind") == "local_endpoint_response"
    )
    connection = project.get("model_connection")
    state = project.get("model_connection_state") or {"status": "disconnected"}
    # A saved ready label never establishes readiness of a changed configuration.
    if state.get("configuration_sha256") != digest:
        state = {"status": "unconfirmed", "reason": "Configuration changed; reconnect explicitly"}
    return {
        "connection": connection,
        "state": state if connection else {"status": "disconnected"},
        "configuration_sha256": digest,
        "evaluation": evaluation,
        "verification": "current_endpoint_observation"
        if current
        else "no_current_endpoint_evidence",
        "model_identity_independently_verified": False,
        "server_managed_by_furnace": False,
        "limits": "HTTP protocol observation only. Declared revision is not independently attested. Exact equality is not semantic quality; duration is non-streaming round trip, not TTFT. No automatic repair/performance verdict.",
    }
