"""Record synthetic everyday tasks through an actual installed app and local model."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from furnace.runtime.catalog import MODELS
from furnace.runtime.scoring import SCORER_VERSION, ScoringRule, score
from furnace_api.desktop import DesktopService


def resource_view(value):
    return {key: value.get(key) for key in ("gpu", "resources", "container")}


def main() -> int:
    parser = argparse.ArgumentParser()
    origin = parser.add_mutually_exclusive_group(required=True)
    origin.add_argument("--installed-build", type=Path)
    origin.add_argument(
        "--source-checkout",
        action="store_true",
        help="Explicit source trial; never labelled installed",
    )
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--group", choices=["injection", "everyday", "longer-document"])
    parser.add_argument(
        "--long-pdf",
        action="store_true",
        help="Actual extraction/answer of a synthetic 25-page text PDF",
    )
    parser.add_argument("--accelerator", choices=["cpu", "nvidia"], default="cpu")
    parser.add_argument("--model", default="qwen2.5-1.5b-instruct-q4_k_m")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing to overwrite an existing trial record")
    import furnace_api

    if args.installed_build:
        installed = args.installed_build.resolve()
        if not Path(sys.executable).resolve().is_relative_to(installed) or not Path(
            furnace_api.__file__
        ).resolve().is_relative_to(installed):
            raise SystemExit("Use the installed runtime/python.exe -I; source imports are refused")
        build = json.loads((installed / "build.json").read_text())
    else:
        root = Path(__file__).resolve().parents[1]
        git = shutil.which("git")
        if not git:
            raise SystemExit("Source provenance requires git")
        build = {
            "kind": "source-checkout",
            "commit": subprocess.check_output(  # noqa: S603 -- resolved git and fixed argv
                [git, "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "source_dirty": bool(
                subprocess.check_output([git, "status", "--porcelain"], cwd=root)  # noqa: S603 -- resolved git and fixed argv
            ),
            "everyday_sha256": hashlib.sha256(
                Path(furnace_api.__file__).with_name("everyday.py").read_bytes()
            ).hexdigest(),
        }
    suite_path = args.suite or Path(furnace_api.__file__).with_name("everyday_suite.json")
    suite_bytes = suite_path.read_bytes()
    suite = json.loads(suite_bytes)
    if args.group:
        suite["cases"] = [c for c in suite["cases"] if c.get("group") == args.group]
    recipe = MODELS[args.model]
    record = {
        "schema": "furnace-everyday-model-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "installed_build": build,
        "os": platform.platform(),
        "python": platform.python_version(),
        "model": args.model,
        "accelerator": args.accelerator,
        "weights_sha256": recipe.weights.sha256,
        "model_revision": recipe.revision,
        "license": recipe.license,
        "suite_sha256": hashlib.sha256(suite_bytes).hexdigest(),
        "scorer": SCORER_VERSION,
        "group": args.group,
        "prompt_mode": "system /no_think"
        if args.model.startswith("qwen3-")
        else "standard system instruction",
        "download_bytes": recipe.weights.size,
        "source_data": "synthetic packaged everyday suite only; no private user documents",
        "cases": [],
        "result": "incomplete",
    }
    workspace = Path(tempfile.mkdtemp(prefix="furnace-everyday-validation-"))
    service = DesktopService(workspace, Path.home() / ".furnace/artifacts")
    try:
        service.start()
        with httpx.Client(
            base_url=service.url,
            headers={"x-furnace-session": service.token},
            timeout=1930,
            trust_env=False,
        ) as client:

            def api(method, path, **kwargs):
                response = client.request(method, "/api/" + path, **kwargs)
                response.raise_for_status()
                return response.json()

            pid = api("POST", "everyday/setup")["id"]
            selection = {
                "model": args.model,
                "accelerator": args.accelerator,
                "threads": 4,
                "memory_mb": 4096,
                "context_tokens": 4096,
                "max_tokens": 512,
                "request_timeout_seconds": 120,
                "evaluation_budget_seconds": 900,
            }
            record["selection"] = selection
            record["docker"] = api("GET", "managed/catalog")["docker"]
            api("PUT", f"projects/{pid}/managed", json=selection)
            api("POST", f"projects/{pid}/managed/prepare", json={"consent": True})
            deadline = time.monotonic() + 1800
            while True:
                state = api("GET", f"projects/{pid}/managed")
                if state["status"] in {"prepared", "failed"}:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Preparation exceeded its recorded trial budget")
                time.sleep(1)
            record["prepare"] = {
                "status": state["status"],
                "reason": state.get("reason"),
                "cache": "shared verified-weights store; verified again before launch",
            }
            if state["status"] != "prepared":
                raise RuntimeError("Preparation failed; see preserved reason")
            ready = api("POST", f"projects/{pid}/managed/start", json={"consent": True})
            record["launch_id"] = ready["launch"]["launch_id"]
            record["observation_before"] = resource_view(
                api("GET", f"projects/{pid}/managed/observe")
            )
            if args.long_pdf:
                fixture = Path(__file__).with_name("long_document_fixture.py")
                pdf = runpy.run_path(str(fixture))["make_pdf"]()
                record["suite_override"] = {
                    "kind": "synthetic-25-page-pdf",
                    "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                }
                began_extract = time.monotonic()
                extracted = api(
                    "POST",
                    "everyday/extract",
                    json={"kind": "pdf", "data": base64.b64encode(pdf).decode()},
                )
                record["pdf"] = {
                    "pages": 25,
                    "sha256": hashlib.sha256(pdf).hexdigest(),
                    "bytes": len(pdf),
                    "text_utf8_bytes": len(extracted["text"].encode()),
                    "extraction_seconds": round(time.monotonic() - began_extract, 3),
                    "ocr": extracted["ocr"],
                    "warning": extracted["warning"],
                }
                suite["cases"] = [
                    {
                        "name": "25-page document",
                        "request": {
                            "action": "summarise",
                            "text": extracted["text"],
                            "question": "State the project owner and final submission deadline exactly as written.",
                        },
                        "scoring": {"method": "contains", "values": ["Maya", "2027-02-19"]},
                    }
                ]
            for case in suite["cases"]:
                began = time.monotonic()
                observed = {"name": case["name"], "operational": "error", "score": "unscored"}
                try:
                    response = client.post(
                        f"/api/everyday/projects/{pid}/answer", json=case["request"]
                    )
                    observed["http_status"] = response.status_code
                    result = response.json()
                    if response.status_code != 200:
                        observed["error"] = result.get("detail", "request_failed")
                    else:
                        observed["operational"] = (
                            "completed"
                            if result["receipt"]["status"] == "checked"
                            else "unverified_receipt"
                        )
                        rule = (
                            ScoringRule.model_validate(case["scoring"]) if case["scoring"] else None
                        )
                        verdict, reason = score(
                            rule, result["output"], None, case["request"]["text"]
                        )
                        observed.update(
                            score=verdict,
                            scoring_reason=reason,
                            output=result["output"],
                            processing=result["processing"],
                            requests=result["requests"],
                            receipt=result["receipt"],
                            warnings=result.get("warnings", []),
                        )
                except (httpx.HTTPError, ValueError) as error:
                    observed["error"] = type(error).__name__
                observed["elapsed_seconds"] = round(time.monotonic() - began, 3)
                record["cases"].append(observed)
                observed["memory_observation"] = resource_view(
                    api("GET", f"projects/{pid}/managed/observe")
                )
                print(
                    case["name"],
                    observed["operational"],
                    observed["score"],
                    observed["elapsed_seconds"],
                    flush=True,
                )
            api("POST", f"projects/{pid}/managed/stop")
            record["result"] = "recorded"  # completion of a trial, not a semantic quality pass
    except Exception as error:
        record["error"] = type(error).__name__
    finally:
        record["shutdown_completed"] = service.stop() if service.thread.ident else True
        record["score_summary"] = {
            status: sum(c["score"] == status for c in record["cases"])
            for status in ("pass", "fail", "unscored")
        }
        record["operationally_complete"] = len(record["cases"]) == len(suite["cases"]) and all(
            c["operational"] == "completed" for c in record["cases"]
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Recorded rule results, not semantic quality:", record["score_summary"], args.out)
    return 0 if record["operationally_complete"] and record["shutdown_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
