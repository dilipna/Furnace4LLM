import pytest
from furnace_api.studio_summary import evidence_summary


def project():
    return {
        "id": "project-one",
        "configuration_sha256": "a" * 64,
        "cases": [{}, {}, {}],
        "evaluation_verification": "no_current_evidence",
        "evaluation": None,
        "model_endpoint": {
            "configuration_sha256": "b" * 64,
            "verification": "no_current_endpoint_evidence",
            "evaluation": None,
        },
    }


def test_empty_export_does_not_imply_any_execution_or_quality():
    summary = evidence_summary(project())
    assert summary.count("No saved attempt") == 2
    assert "not a live health check" in summary
    assert "not model TTFT" in summary
    assert "do not establish semantic quality" in summary


@pytest.mark.parametrize("kind", ["fixture", "endpoint"])
def test_completed_attempt_keeps_failed_unscored_and_missing_cases_distinct(kind):
    value = project()
    run = {
        "project_id": value["id"],
        "run_id": "saved-run",
        "status": "completed",
        "configuration_sha256": "a" * 64,
        "results": [
            {"status": "check_fail", "output": "PRIVATE OUTPUT"},
            {"status": "unscored", "input": "PRIVATE PROMPT"},
        ],
    }
    if kind == "fixture":
        value.update(evaluation=run, evaluation_verification="current_framework_evidence")
    else:
        run["configuration_sha256"] = value["model_endpoint"]["configuration_sha256"]
        value["model_endpoint"].update(evaluation=run, verification="current_endpoint_observation")
    summary = evidence_summary(value)
    assert "**completed**. Completion alone does not mean its checks passed" in summary
    assert "| check_fail | 1 |" in summary and "| unscored | 1 |" in summary
    assert "Missing result rows: 1" in summary
    assert "PRIVATE" not in summary


def test_interrupted_stale_attempt_uses_its_original_count_not_current_cases():
    value = project()
    value["model_endpoint"]["evaluation"] = {
        "status": "interrupted",
        "case_count": 5,
        "results": [{"status": "error"}],
        "configuration_sha256": "c" * 64,
    }
    summary = evidence_summary(value)
    assert "**interrupted**" in summary
    assert "**unbound or stale; does not verify this configuration**" in summary
    assert "Missing result rows: 4" in summary
    del value["model_endpoint"]["evaluation"]["case_count"]
    assert "Missing result rows: not recorded" in evidence_summary(value)


def test_summary_does_not_render_untrusted_identifiers_or_invent_unknown_status_passes():
    value = project()
    value["evaluation"] = {
        "run_id": "<script>PRIVATE</script>",
        "status": "PRIVATE VERDICT",
        "results": [{"status": "PRIVATE OUTCOME"}],
        "configuration_sha256": "```PRIVATE",
    }
    summary = evidence_summary(value)
    assert "PRIVATE" not in summary
    assert "Saved attempt: **unknown**" in summary
    assert "| unrecognized status | 1 |" in summary


@pytest.mark.parametrize(
    "patch", [{"project_id": "another-project"}, {"configuration_sha256": "c" * 64}]
)
def test_inconsistent_identity_cannot_be_presented_as_current(patch):
    value = project()
    value.update(
        evaluation_verification="current_framework_evidence",
        evaluation={
            "project_id": value["id"],
            "configuration_sha256": value["configuration_sha256"],
            "status": "completed",
            "results": [],
            **patch,
        },
    )
    summary = evidence_summary(value)
    assert "Binding: matches" not in summary
    assert "unbound or stale" in summary
    assert "Missing result rows: not recorded" in summary
