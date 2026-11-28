"""Authored metadata around historical record shapes; these tests run no inference."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "installed_acceptance", ROOT / "scripts/check_installed_acceptance.py"
)
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def evidence(tmp_path):
    historical = ROOT / "docs/release/installer-verification/candidate-9598d6d"
    metadata = json.loads((historical / "installer.json").read_text(encoding="utf-8"))
    binary = tmp_path / metadata["file"]
    binary.write_bytes(b"authored unit-test installer, not executable")
    metadata.update(
        bytes=binary.stat().st_size, sha256=hashlib.sha256(binary.read_bytes()).hexdigest()
    )
    (tmp_path / "installer.json").write_text(json.dumps(metadata))
    paths = {
        "studio_install": "install.json",
        "document_install": "document-2026-11-28/install.json",
        "smoke": "installed-smoke.json",
        "qwen": "qwen-cpu.json",
        "granite": "granite-cpu.json",
        "document_suite": "document-2026-11-28/everyday-cpu.json",
        "document_ui": "document-2026-11-28/browser-3/record.json",
        "suite": "document-2026-11-28/suite.json",
    }
    plan = {"schema": "furnace-installed-acceptance-inputs-v1"}
    for name, original in paths.items():
        data = (historical / original).read_bytes()
        if name != "suite":
            record = json.loads(data)
            if "installer_sha256" in record:
                record["installer_sha256"] = metadata["sha256"]
            if name == "smoke":
                # Authored positive fixture only: historical smoke predates this check.
                record["checks"]["project_notice_matches_source"] = True
            data = json.dumps(record).encode()
        filename = name + ".json"
        (tmp_path / filename).write_bytes(data)
        plan[name] = filename
    manifest = tmp_path / "inputs.json"
    manifest.write_text(json.dumps(plan))
    return tmp_path / "installer.json", binary, manifest, metadata["commit"]


def change(evidence, name, mutate):
    path = evidence[2].parent / (name + ".json")
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))


def test_matching_records_keep_unfavorable_quality_and_do_not_authorize_release(evidence):
    report = checker.verify(*evidence)
    assert report["studio_quality"]["qwen"]["failed"] == 1
    assert report["studio_quality"]["granite"]["failed"] == 5
    assert report["document_quality"]["fail"] == 5
    assert report["document_planned"] == 42
    assert report["publication_authorized"] is False
    assert report["human_gates"] == "not assessed"


def test_another_binary_or_expected_source_is_refused(evidence):
    original = evidence[1].read_bytes()
    with pytest.raises(ValueError, match="expected commit"):
        checker.verify(*evidence[:3], "different-source")
    evidence[1].write_bytes(b"changed binary")
    with pytest.raises(ValueError, match=r"size|SHA-256"):
        checker.verify(*evidence)
    evidence[1].write_bytes(bytes([original[0] ^ 1]) + original[1:])
    with pytest.raises(ValueError, match="SHA-256"):
        checker.verify(*evidence)


def test_same_commit_different_build_cannot_reuse_model_records(evidence):
    change(evidence, "qwen", lambda r: r["installed_build"].update(built_at="different-build"))
    with pytest.raises(ValueError, match="built_at"):
        checker.verify(*evidence)


def test_completed_label_cannot_hide_missing_case_execution(evidence):
    change(evidence, "qwen", lambda r: r["steps"]["evaluation_1"]["per_case"].pop())
    with pytest.raises(ValueError, match="missing evaluated cases"):
        checker.verify(*evidence)


@pytest.mark.parametrize("name", ["studio_install", "document_install", "document_ui"])
def test_installer_hash_must_match_every_artifact_binding(evidence, name):
    change(evidence, name, lambda r: r.update(installer_sha256="another-installer"))
    with pytest.raises(ValueError, match="installer"):
        checker.verify(*evidence)


def test_crash_and_restart_must_have_actual_interruption_and_new_launch(evidence):
    change(
        evidence, "qwen", lambda r: r["steps"]["crash_during_evaluation"].update(status="completed")
    )
    with pytest.raises(ValueError, match="crash evidence"):
        checker.verify(*evidence)


def test_restart_cannot_be_the_same_launch(evidence):
    def mutate(record):
        repeat = record["steps"]["restart"]["reproducibility"]
        repeat["current_launch_id"] = repeat["reference_launch_id"]

    change(evidence, "qwen", mutate)
    with pytest.raises(ValueError, match="reused launch"):
        checker.verify(*evidence)


@pytest.mark.parametrize("field", ["project_notice_matches_source", "kit_export_through_ui"])
def test_missing_installed_checks_are_not_assumed(evidence, field):
    change(evidence, "smoke", lambda r: r["checks"].pop(field))
    with pytest.raises(ValueError, match="missing/failed check"):
        checker.verify(*evidence)


def test_document_suite_cannot_discard_a_failed_case(evidence):
    change(evidence, "document_suite", lambda r: r["cases"].pop())
    with pytest.raises(ValueError, match="document cases"):
        checker.verify(*evidence)


@pytest.mark.parametrize("journey", ["studio", "documents"])
def test_reducing_the_plan_as_well_as_results_cannot_hide_undercoverage(evidence, journey):
    if journey == "studio":

        def reduce_studio(record):
            steps = record["steps"]
            steps["suite"]["cases"] = 1
            for name in ("evaluation_1", "evaluation_2"):
                evaluation = steps[name]
                evaluation.update(per_case=evaluation["per_case"][:1], passed=1, failed=0)
            steps["outputs"]["cases"] = steps["outputs"]["cases"][:1]
            steps["outputs"]["identical_to_evaluation"] = 1
            for phase in (steps["evaluation_2"], steps["restart"]):
                phase["reproducibility"].update(compared=1, identical=1)

        change(evidence, "qwen", reduce_studio)
        expected = "all 12 cases"
    else:
        folder = evidence[2].parent
        suite = json.loads((folder / "suite.json").read_text())
        suite["cases"] = suite["cases"][:1]
        data = json.dumps(suite).encode()
        (folder / "suite.json").write_bytes(data)

        def mutate(record):
            record["cases"] = record["cases"][:1]
            record["suite_sha256"] = hashlib.sha256(data).hexdigest()
            record["score_summary"] = {"pass": 1, "fail": 0, "unscored": 0}

        change(evidence, "document_suite", mutate)
        expected = "all 42 cases"
    with pytest.raises(ValueError, match=expected):
        checker.verify(*evidence)


def test_score_labels_cannot_overrule_actual_case_counts(evidence):
    change(
        evidence,
        "document_suite",
        lambda r: r.update(score_summary={"pass": 42, "fail": 0, "unscored": 0}),
    )
    with pytest.raises(ValueError, match="score totals"):
        checker.verify(*evidence)


def test_unknown_score_cannot_be_hidden_outside_the_denominator(evidence):
    change(evidence, "document_suite", lambda r: r["cases"][0].update(score="ignored"))
    with pytest.raises(ValueError, match="unknown document score"):
        checker.verify(*evidence)


@pytest.mark.parametrize("mutation", ["missing_request", "changed_output", "failed_rule"])
def test_browser_needs_actual_output_requests_and_rule_outcomes(evidence, mutation):
    def mutate(record):
        answer = record["answers"][0]
        if mutation == "missing_request":
            answer["actual_response"]["requests"] = []
        elif mutation == "changed_output":
            answer["output"] = "different output"
        else:
            answer["rule_passed"] = False

    change(evidence, "document_ui", mutate)
    with pytest.raises(ValueError, match="browser"):
        checker.verify(*evidence)


def test_non_finite_values_are_refused(evidence):
    change(
        evidence, "qwen", lambda r: r["steps"]["evaluation_1"].update(elapsed_seconds=float("nan"))
    )
    with pytest.raises(ValueError, match="non-finite"):
        checker.verify(*evidence)
