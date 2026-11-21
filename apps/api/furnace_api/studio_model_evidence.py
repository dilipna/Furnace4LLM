"""Identity of endpoint observations, kept separate from infrastructure-fixture evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

PROTOCOL = "local-chat-v1"
HISTORY_LIMIT = 10
CASE_KEYS = ("name", "input", "expected_behavior", "expected_output", "scoring")
# Per-launch values of a Furnace-operated server: a restart of the same pinned
# manifest is the same configuration, so its runs stay comparable.
VOLATILE_MANAGED_KEYS = {"base_url", "launch_id"}


def case_input(case: dict[str, Any]) -> dict[str, Any]:
    value = {key: case.get(key) for key in CASE_KEYS}
    if value["scoring"] is None:
        del value["scoring"]  # identities of cases saved before scoring rules stay unchanged
    return value


def retained_runs(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Oldest to newest, including the last run from previews without a history field."""
    records = {}
    for run in [*project.get("model_evaluation_history", []), project.get("model_evaluation")]:
        if (
            isinstance(run, dict)
            and isinstance(run.get("run_id"), str)
            and run.get("project_id") == project["id"]
        ):
            records[run["run_id"]] = run
    return list(records.values())[-HISTORY_LIMIT:]


def matches(project: dict[str, Any], evaluation: dict[str, Any], digest: str) -> bool:
    return (
        evaluation.get("project_id") == project["id"]
        and evaluation.get("configuration_sha256") == digest
        and evaluation.get("protocol") == PROTOCOL
        and evaluation.get("execution_kind") == "local_endpoint_response"
    )


def connection_identity(connection: dict[str, Any] | None) -> dict[str, Any] | None:
    if not connection or not connection.get("managed"):
        return connection
    return {k: v for k, v in connection.items() if k not in VOLATILE_MANAGED_KEYS}


def identity(project: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "project_id": project["id"],
                "contract": project["contract"],
                "plan": project["plan"],
                "cases": [case_input(c) for c in project["cases"]],
                "connection": connection_identity(project.get("model_connection")),
                "protocol": PROTOCOL,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def reproducibility(
    runs: list[dict[str, Any]], current: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Compare output hashes with the previous completed run of the same configuration."""
    if not current or current.get("status") != "completed":
        return None
    earlier = [
        r
        for r in runs
        if r.get("run_id") != current.get("run_id")
        and r.get("status") == "completed"
        and r.get("configuration_sha256") == current.get("configuration_sha256")
        and r.get("at", "") < current.get("at", "")
    ]
    if not earlier:
        return {"status": "no_earlier_run", "compared": 0, "identical": 0}
    reference = earlier[-1]
    before = {r["case_index"]: r.get("output_sha256") for r in reference.get("results", [])}
    pairs = [
        (r.get("output_sha256"), before.get(r["case_index"]))
        for r in current.get("results", [])
        if r.get("output_sha256") and before.get(r["case_index"])
    ]
    identical = sum(1 for now, then in pairs if now == then)
    return {
        "status": "identical" if pairs and identical == len(pairs) else "diverged",
        "reference_run_id": reference.get("run_id"),
        "reference_launch_id": reference.get("launch_id"),
        "current_launch_id": current.get("launch_id"),
        "compared": len(pairs),
        "identical": identical,
    }


def view(project: dict[str, Any]) -> dict[str, Any]:
    digest = identity(project)
    evaluation = project.get("model_evaluation")
    current = bool(evaluation and matches(project, evaluation, digest))
    connection = project.get("model_connection")
    managed = bool(connection and connection.get("managed"))
    # Older managed records predate the flag; they always came from pinned recipes.
    verified = managed and bool(
        ((connection or {}).get("server") or {}).get("weights_verified", True)
    )
    state = project.get("model_connection_state") or {"status": "disconnected"}
    # A saved ready label never establishes readiness of a changed configuration.
    if state.get("configuration_sha256") != digest:
        state = {"status": "unconfirmed", "reason": "Configuration changed; reconnect explicitly"}
    runs = retained_runs(project)
    return {
        "connection": connection,
        "state": state if connection else {"status": "disconnected"},
        "configuration_sha256": digest,
        "evaluation": evaluation,
        "reproducibility": reproducibility(runs, evaluation) if current else None,
        "history": [
            {**run, "matches_current_configuration": matches(project, run, digest)} for run in runs
        ],
        "history_limit": HISTORY_LIMIT,
        "verification": "current_endpoint_observation"
        if current
        else "no_current_endpoint_evidence",
        "model_identity_independently_verified": False,
        "weights_verified_before_launch": verified,
        "server_managed_by_furnace": managed,
        "limits": (
            "Furnace launched this pinned manifest and verified the weights' SHA-256 before "
            "mounting them read-only; it does not attest the running process further. "
            if verified
            else "Furnace launched your adapter image and digested its code; weights are recorded "
            "by name and size, not hash-verified. "
            if managed
            else "HTTP protocol observation only. Declared revision is not independently attested. "
        )
        + "Rule checks (exact, contains, numeric, choice, regex, JSON fields) are not human "
        "quality judgements; duration is a non-streaming round trip, not TTFT. "
        "No automatic repair/performance verdict.",
    }
