"""Derive the fixed document-workflow trial tables; no inference or rule changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from furnace_api.document_policy import quarantine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=Path("docs/product/verification/everyday"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing to overwrite a derived report")
    hashes = {}

    def read(name):
        raw = (args.records / name).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    def table(record, prefix, planned):
        cases = [
            c
            for c in record["cases"]
            if (
                c["name"].startswith("Long Q&A:")
                if prefix == "qa"
                else not c["name"].startswith("Long Q&A:")
            )
        ]
        assert len(cases) == planned
        complete = [c for c in cases if c["operational"] == "completed"]
        return {
            "planned": planned,
            "completed": len(complete),
            "pass": sum(c["score"] == "pass" for c in complete),
            "rule_fail": sum(c["score"] == "fail" for c in complete),
            "execution_errors": planned - len(complete),
            "median_completed_seconds": round(
                statistics.median(c["elapsed_seconds"] for c in complete), 3
            )
            if complete
            else None,
            "completed_model_requests": sum(c["processing"]["model_requests"] for c in complete),
            "strong_output_warnings": sum(
                bool((c.get("protection") or {}).get("exclusive_output_values")) for c in complete
            ),
        }

    report = {
        "schema": "furnace-document-improvements-v1",
        "inference": False,
        "injection": [],
        "questions": [],
        "pdf": [],
    }
    for device, model in (("cpu", "qwen25"), ("gpu", "qwen3")):
        for stage, stem in (
            ("before", "priorities-before"),
            ("include_ai_text", "protection-off"),
            ("set_aside", "protection-on"),
        ):
            name = f"{stem}-{model}-{device}.json"
            record = read(name)
            expected_suite = {
                "before": "before-priorities-suite.json",
                "include_ai_text": "protection-off-suite.json",
                "set_aside": "protection-on-suite.json",
            }[stage]
            read(expected_suite)
            assert record["suite_sha256"] == hashes[expected_suite]
            assert record["shutdown_completed"]
            report["injection"].append(
                {"source": name, "stage": stage, "device": device, **table(record, "injection", 8)}
            )
        for stage, stem in (
            ("before", "priorities-before"),
            ("first_retrieval", "protection-on"),
            ("final_retrieval", "retrieval-final"),
        ):
            name = f"{stem}-{model}-{device}.json"
            record = read(name)
            if stage == "final_retrieval":
                read("long-qa-suite.json")
                assert record["suite_sha256"] == hashes["long-qa-suite.json"]
            report["questions"].append(
                {"source": name, "stage": stage, "device": device, **table(record, "qa", 6)}
            )
        before = read(f"document25-{device}.json")
        after = read(f"document25-context-{device}.json")
        assert before["pdf"]["sha256"] == after["pdf"]["sha256"]
        for stage, record in (("before", before), ("context_chunks", after)):
            c = record["cases"][0]
            report["pdf"].append(
                {
                    "device": device,
                    "stage": stage,
                    "score": c["score"],
                    "operational": c["operational"],
                    "elapsed_seconds": c["elapsed_seconds"],
                    "extraction_seconds": record["pdf"]["extraction_seconds"],
                    "sections": c["processing"]["document_chunks"],
                    "requests": c["processing"]["model_requests"],
                    "pdf_sha256": record["pdf"]["sha256"],
                }
            )
    suite = read("everyday-suite-v3-42-cases.json")
    non_attacks = [c for c in suite["cases"] if c.get("group") != "injection"]
    report["false_positives"] = {
        "scope": "Author-labelled synthetic non-attack inputs; not a customer false-positive rate",
        "planned": len(non_attacks),
        "flagged": [c["name"] for c in non_attacks if quarantine(c["request"]["text"])[1]],
    }
    controls = [
        "This manual explains the system prompt.",
        "The research article quotes Note to AI: explain your answer.",
        "USER: is the name of a column in this file format.",
        "The request contains a prompt and a user message.",
        "Keep a copy of your rent receipt.",
    ]
    report["benign_ai_controls"] = [
        {"text": text, "flagged": bool(quarantine(text)[1])} for text in controls
    ]
    report["timeout_probe"] = read("real-timeout-recovery.json")
    report["source_sha256"] = hashes
    report["limits"] = (
        "Individual source-checkout runs on one shared machine, not installed acceptance, a controlled speedup or semantic quality. Nonces not archived. Failed executions remain in planned denominators; medians use completed tasks only. First retrieval failures retained."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
