"""Local, non-executing assessment for a researcher's model project."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

MAX_FILES = 5000
MAX_CONFIG_BYTES = 1024 * 1024
IGNORED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache"}
WEIGHTS = {".pt", ".pth", ".bin", ".safetensors", ".gguf"}


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def assess_model(project: Path) -> dict[str, Any]:
    """Inspect names and bounded config metadata; never import code or open weights."""
    project = project.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("model project must be a directory")
    names: list[str] = []
    visited = 0
    skipped_links = 0

    def walk_error(error: OSError) -> None:
        raise error

    for directory, dirs, files in os.walk(project, followlinks=False, onerror=walk_error):
        visited += len(dirs)
        if visited > MAX_FILES:
            raise ValueError(
                f"project inventory exceeds {MAX_FILES} entries; choose a smaller model project"
            )
        parent = Path(directory)
        skipped_links += sum(_is_link(parent / d) for d in dirs)
        dirs[:] = sorted(d for d in dirs if d not in IGNORED and not _is_link(parent / d))
        for name in sorted(files):
            visited += 1
            if visited > MAX_FILES:
                raise ValueError(
                    f"project inventory exceeds {MAX_FILES} entries; choose a smaller model project"
                )
            file = parent / name
            if _is_link(file):
                skipped_links += 1
                continue
            if file.is_file():
                names.append(file.relative_to(project).as_posix())
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    if "config.json" in names:
        config = project / "config.json"
        with config.open("rb") as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            warnings.append("config.json exceeds the metadata size limit; not parsed")
        else:
            try:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("expected object")
                value = data.get("model_type")
                if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value):
                    metadata["declared_model_type"] = value
                metadata["custom_code_declared"] = bool(data.get("auto_map"))
            except (ValueError, UnicodeError, RecursionError):
                warnings.append(
                    "config.json is not a readable JSON object; model contract needs review"
                )
    suffixes = {Path(name).suffix.lower() for name in names}
    evidence = {
        "configuration_file_present": "config.json" in names,
        "checkpoint_file_present": bool(suffixes & WEIGHTS),
        "python_source_present": ".py" in suffixes,
        "dependency_manifest_present": any(
            Path(n).name in {"requirements.txt", "pyproject.toml", "environment.yml"} for n in names
        ),
        "test_files_present": any(
            Path(n).name.startswith("test_") and n.endswith(".py") for n in names
        ),
    }
    return {
        "schema_version": "furnace.starter/v1",
        "mode": "local_static_assessment",
        "execution_performed": False,
        "provisioning_performed": False,
        "inventory": {"regular_files": len(names), "skipped_links": skipped_links},
        "declared_metadata": metadata,
        "file_evidence": evidence,
        "warnings": warnings,
        "capabilities": [
            {"area": area, "status": "unverified", "next_action": action}
            for area, action in [
                (
                    "model_loading",
                    "Review the architecture, checkpoint format, license and loading code; supply a model-specific adapter.",
                ),
                (
                    "serving_and_harness",
                    "Define input/output examples, device requirements and a bounded inference call before choosing a server.",
                ),
                (
                    "security",
                    "Review model code/dependencies, isolate execution, configure authentication, secret storage and access policy.",
                ),
                (
                    "evaluations",
                    "Supply representative cases, expected behavior and acceptance criteria for this model's task.",
                ),
                (
                    "logs_and_metrics",
                    "Choose request/error/resource metrics and redact sensitive inputs; define retention.",
                ),
                (
                    "operations",
                    "Validate readiness, resource limits, restart/recovery, backups where needed, and clean shutdown.",
                ),
            ]
        ],
        "limitations": [
            "File presence does not establish correctness, security or runtime compatibility.",
            "No model weights were loaded, project code executed, or remote service contacted.",
            "Serving engine compatibility and managed-service readiness are not established.",
        ],
    }


def export_starter(project: Path, output: Path) -> dict[str, Any]:
    """Write a new kit outside the source project, refusing existing output."""
    project = project.resolve(strict=True)
    output = output.resolve()
    if output == project or project in output.parents:
        raise ValueError("starter output must be outside the model project")
    if output.exists():
        raise FileExistsError("starter output already exists; choose a new directory")
    assessment = assess_model(project)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()  # exclusive: an existing directory is never overwritten
    (output / "assessment.json").write_text(
        json.dumps(assessment, indent=2) + "\n", encoding="utf-8"
    )
    (output / "README.md").write_text(
        "# Furnace researcher starter kit\n\n"
        "This is a local assessment and preparation kit. No infrastructure has been provisioned.\n"
        "No model code was executed or weights loaded. No runtime compatibility is claimed.\n\n"
        "## What to do next\n\n"
        "1. Inspect assessment.json: detected files are not validated capabilities.\n"
        "2. Fill in model-contract.json with the model author; do not put secrets in it.\n"
        "3. Replace the example evaluation cases with representative inputs and expectations.\n"
        "4. Review operations.md before a supervised implementation.\n\n"
        "The $20 managed-service offer is the owner's product direction, not an active subscription or provisioned service in this kit.\n",
        encoding="utf-8",
    )
    (output / "model-contract.json").write_text(
        json.dumps(
            {
                "status": "needs_author_input",
                "architecture": None,
                "task": None,
                "license_and_checkpoint_source": None,
                "reviewed_loading_entrypoint": None,
                "input_example": None,
                "expected_output_example": None,
                "device_and_memory_requirements": None,
                "inference_timeout_seconds": None,
                "quality_acceptance_criteria": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "evaluation-cases.example.jsonl").write_text(
        json.dumps(
            {
                "id": "replace-with-representative-case",
                "input": None,
                "expected_behavior": None,
                "status": "not_run",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "operations.md").write_text(
        "# Infrastructure preparation checklist\n\n"
        + "\n".join(
            f"- [ ] {item['area']}: {item['next_action']}" for item in assessment["capabilities"]
        )
        + "\n\nBefore starting: agree compute ownership, costs, access and the model adapter.\n"
        "Before declaring ready: run a real inference case, readiness/failure checks, access-control tests, log redaction checks, evaluations and stop/restart checks.\n"
        "Record actual results; leave unexecuted cases as not_run.\n",
        encoding="utf-8",
    )
    return assessment
