"""Derive a comparison from every supplied raw trial, including failures. No inference."""

import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path


def memory_bytes(text):
    match = re.fullmatch(r"([\d.]+)(B|KiB|MiB|GiB)", text.split(" / ")[0])
    if not match:
        return 0
    return float(match[1]) * {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}[match[2]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("records", nargs="+", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    suite_raw = args.suite.read_bytes()
    suite = json.loads(suite_raw)
    attacks = {c["name"] for c in suite["cases"] if c["group"] == "injection"}
    rows = []
    for path in args.records:
        raw = path.read_bytes()
        trial = json.loads(raw)
        assert trial["suite_sha256"] == hashlib.sha256(suite_raw).hexdigest()
        assert {c["name"] for c in trial["cases"]} == {c["name"] for c in suite["cases"]}
        assert len(trial["cases"]) == len(suite["cases"])
        complete = [c for c in trial["cases"] if c["operational"] == "completed"]
        samples = [trial.get("observation_before", {})] + [
            c.get("memory_observation", {}) for c in trial["cases"]
        ]
        rows.append(
            {
                "source": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "execution": trial["installed_build"],
                "model": trial["model"],
                "accelerator": trial["accelerator"],
                "planned": len(suite["cases"]),
                "completed": len(complete),
                "pass": sum(c["score"] == "pass" for c in trial["cases"]),
                "rule_fail": sum(c["score"] == "fail" for c in trial["cases"]),
                "execution_errors": len(trial["cases"]) - len(complete),
                "injection_pass": sum(
                    c["score"] == "pass" for c in trial["cases"] if c["name"] in attacks
                ),
                "injection_planned": len(attacks),
                "median_completed_seconds": round(
                    statistics.median(c["elapsed_seconds"] for c in complete), 3
                )
                if complete
                else None,
                "median_scope": "whole suite"
                if len(complete) == len(suite["cases"])
                else "completed tasks only; NOT a full-suite median",
                "max_sampled_container_gib": round(
                    max(
                        memory_bytes((s.get("resources") or {}).get("memory", "0B"))
                        for s in samples
                    )
                    / 1024**3,
                    3,
                ),
                "max_sampled_device_gpu_mib": max(
                    ((s.get("gpu") or {}).get("memory_used_mib", 0) for s in samples), default=0
                )
                or None,
                "download_bytes": trial["download_bytes"],
                "scorer": trial["scorer"],
                "shutdown_completed": trial["shutdown_completed"],
            }
        )
    report = {
        "schema": "furnace-everyday-comparison-v1",
        "rows": rows,
        "limits": "Single trials on a shared Windows host, not controlled performance/causal estimates. Some developer builds and unrelated workloads ran concurrently. Latencies include HTTP, observed isolation and staged processing, exclude preparation/loading and between-task resource sampling. Memory is maximum of before/after-task samples, not a continuous peak; GPU values are device-wide and include other consumers. Pass denominator includes all planned tasks; execution failures are not excluded. Rules are not semantic quality. Eight fixed attacks do not establish general injection resistance. Source trials are not installed-build acceptance.",
    }
    if args.out.exists():
        raise SystemExit("Refusing to overwrite an existing comparison report")
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(
            row["model"],
            row["accelerator"],
            f"{row['pass']}/{row['planned']}",
            f"injection {row['injection_pass']}/{row['injection_planned']}",
            row["median_completed_seconds"],
            row["median_scope"],
            row["max_sampled_container_gib"],
            row["max_sampled_device_gpu_mib"],
        )


if __name__ == "__main__":
    main()
