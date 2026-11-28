"""Check recorded final-installer evidence consistency; never authorize publication.

No inference is run. Records are trusted observations, not cryptographic attestation.
Human install/pilot and owner publication approval remain separate requirements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path: Path):
    def invalid_constant(value):
        raise ValueError(f"non-finite JSON value: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid_constant)


def true_checks(data, names):
    for name in names:
        require(data["checks"].get(name) is True, f"missing/failed check: {name}")


def verify(metadata: Path, installer: Path, manifest: Path, expected_commit: str):
    info = read(metadata)
    require(info.get("schema") == "furnace-windows-installer-v1", "unknown installer schema")
    require(info["commit"] == expected_commit, "installer source differs from expected commit")
    require(info.get("source_dirty") is False, "installer source is not clean")
    require(installer.name == info["file"], "installer filename differs")
    require(installer.stat().st_size == info["bytes"], "installer size differs")
    with installer.open("rb") as handle:
        require(
            hashlib.file_digest(handle, "sha256").hexdigest() == info["sha256"],
            "installer SHA-256 differs",
        )
    plan = read(manifest)
    require(plan["schema"] == "furnace-installed-acceptance-inputs-v1", "unknown input schema")

    def record(name):
        path = (manifest.parent / plan[name]).resolve()
        require(
            path.is_relative_to(manifest.parent.resolve()),
            f"record outside evidence folder: {name}",
        )
        return read(path)

    def same_build(build):
        require(
            build.get("schema") == "furnace-windows-installer-v1",
            "source-checkout evidence is not installed evidence",
        )
        for field in ("commit", "built_at", "version", "python", "platform", "wheel_sha256"):
            require(build.get(field) == info[field], f"installed build differs: {field}")
        require(build.get("source_dirty") is False, "dirty installed provenance")

    # A source SHA alone is insufficient: build time and wheel identities must match
    # the original installer's manifest, and installation receipts bind its full hash.
    for key in ("studio_install", "document_install"):
        installed = record(key)
        require(installed["source_commit"] == expected_commit, f"{key} source differs")
        require(installed["installer_sha256"] == info["sha256"], f"{key} installer differs")
        require(installed["installer_exit_code"] == 0, f"{key} installation failed")
    smoke = record("smoke")
    same_build(smoke["build"])
    require(smoke["completed"] is True, "installed smoke incomplete")
    true_checks(
        smoke,
        (
            "project_notice_matches_source",
            "kit_export_through_ui",
            "no_browser_errors",
            "quit_and_lease_released",
        ),
    )

    quality = {}
    for name, model in (
        ("qwen", "qwen2.5-0.5b-instruct-q8_0"),
        ("granite", "granite-4.0-h-350m-q8_0"),
    ):
        trial = record(name)
        same_build(trial["installed_build"])
        require(
            trial["model"] == model and trial["accelerator"] == "cpu", f"wrong {name} model/device"
        )
        require(trial["completed"] is True and not trial["failures"], f"{name} incomplete")
        steps = trial["steps"]
        count = steps["suite"]["cases"]
        require(
            type(count) is int and count == 12, "release Studio suite must contain all 12 cases"
        )
        for key in ("evaluation_1", "evaluation_2"):
            evaluation = steps[key]
            require(
                evaluation["status"] == "completed"
                and evaluation["incomplete"] == evaluation["errors"] == 0,
                f"{name} evaluation incomplete",
            )
            actual = Counter(case["status"] for case in evaluation["per_case"])
            require(len(evaluation["per_case"]) == count, f"{name} missing evaluated cases")
            require(set(actual) <= {"check_pass", "check_fail"}, f"{name} unfinished case")
            require(
                actual["check_pass"] == evaluation["passed"]
                and actual["check_fail"] == evaluation["failed"],
                f"{name} score totals contradict cases",
            )
            require(
                evaluation["passed"] + evaluation["failed"] == count,
                f"{name} score denominator differs",
            )
        outputs = steps["outputs"]
        require(
            len(outputs["cases"]) == count
            and all(case["matches_evaluated_hash"] is True for case in outputs["cases"]),
            f"{name} output hash comparison missing",
        )
        for phase in (steps["evaluation_2"], steps["restart"]):
            repeat = phase["reproducibility"]
            require(
                repeat["compared"] == repeat["identical"] == count,
                f"{name} repeat outputs differ or are incomplete",
            )
        restart = steps["restart"]["reproducibility"]
        require(
            restart["reference_launch_id"] != restart["current_launch_id"],
            f"{name} restart reused launch",
        )
        crash = steps["crash_during_evaluation"]
        require(
            crash["status"] == "interrupted"
            and crash["last"]["status"] == "error"
            and crash["managed_status"] == "failed",
            f"{name} crash evidence contradicts interruption",
        )
        true_checks(crash, ("no hidden retry after the crash", "crashed server cleaned up"))
        true_checks(
            steps["studio_crash"],
            ("reopen removed the orphaned containers", "reopen never reconnects by itself"),
        )
        true_checks(steps["observe"], ("server metrics collected", "server log omits the key"))
        true_checks(
            steps["export"],
            (
                "exported manifest matches its recorded digest",
                "export omits keys",
                "database omits keys",
                "operations log omits keys",
            ),
        )
        true_checks(steps["stop"], ("stop removed every container",))
        quality[name] = {
            "passed": steps["evaluation_1"]["passed"],
            "failed": steps["evaluation_1"]["failed"],
            "planned": count,
        }

    document = record("document_suite")
    same_build(document["installed_build"])
    require(
        document["model"] == "qwen2.5-1.5b-instruct-q4_k_m" and document["accelerator"] == "cpu",
        "wrong document model/device",
    )
    suite_path = (manifest.parent / plan["suite"]).resolve()
    require(suite_path.is_relative_to(manifest.parent.resolve()), "suite outside evidence folder")
    require(
        hashlib.sha256(suite_path.read_bytes()).hexdigest() == document["suite_sha256"],
        "document suite digest differs",
    )
    suite = read(suite_path)
    require(len(suite["cases"]) == 42, "release document suite must contain all 42 cases")
    require(
        bool(suite["cases"])
        and [c["name"] for c in suite["cases"]] == [c["name"] for c in document["cases"]],
        "document cases missing, duplicated or reordered",
    )
    require(document["shutdown_completed"] is True, "document shutdown failed")
    actual = Counter()
    for case in document["cases"]:
        require(
            case["score"] in {"pass", "fail", "unscored"},
            "unknown document score would hide a case",
        )
        require(
            case["operational"] == "completed" and case["http_status"] == 200,
            "document task did not execute",
        )
        receipt = case["receipt"]
        require(
            receipt["status"] == "checked" and receipt["model"]["id"] == document["model"],
            "unchecked/wrong-model document receipt",
        )
        require(
            receipt["launch_id"] == document["launch_id"], "document receipt from another launch"
        )
        require(case["requests"], "document task has no measured request")
        actual[case["score"]] += 1
    require(
        {key: actual[key] for key in ("pass", "fail", "unscored")} == document["score_summary"],
        "document score totals contradict cases",
    )

    ui = record("document_ui")
    same_build(ui["installed_build"])
    require(ui["installer_sha256"] == info["sha256"], "browser used another installer")
    require(
        ui["model"] == document["model"] and ui["accelerator"] == "cpu",
        "browser model/device differs",
    )
    true_checks(
        ui,
        (
            "installed_module_ownership",
            "studio_to_document_example_navigation",
            "explicit_ui_prepare_start_cpu",
            "actual_pdf_extraction",
            "clear_removes_source_and_answers",
            "reload_clears_content_preserves_model_binding",
            "injection_warning_visible_on_answer",
            "set_aside_visible_before_inference",
            "explicit_ui_stop_confirmed_by_api_state",
            "stopped_request_refused_before_inference_without_restart",
            "quit_and_lease_released",
            "no_browser_errors",
        ),
    )
    require(
        [a["name"] for a in ui["answers"]] == ["summary", "deadline", "missing-info", "injection"],
        "browser task coverage incomplete",
    )
    for answer in ui["answers"]:
        require(answer["rule_passed"] is True, "browser acceptance rule failed")
        result = answer["actual_response"]
        require(
            result["output"] == answer["output"] and result["requests"],
            "browser output lacks matching measured execution",
        )
        require(
            result["receipt"]["status"] == "checked"
            and result["receipt"]["model"]["id"] == ui["model"],
            "browser receipt unchecked or from another model",
        )
    require(ui["stopped_response"]["status"] == 409, "stopped request was not refused")
    return {
        "status": "machine_evidence_consistent",
        "commit": expected_commit,
        "installer_sha256": info["sha256"],
        "studio_quality": quality,
        "document_quality": document["score_summary"],
        "document_planned": len(suite["cases"]),
        "human_gates": "not assessed",
        "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    try:
        result = verify(args.metadata, args.installer, args.records, args.expected_commit)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(
            json.dumps({"status": "blocked", "reason": str(error), "publication_authorized": False})
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
