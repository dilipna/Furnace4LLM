"""Independently check the saved campaign's denominators and paired workloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify(campaign: str, *, write_result: bool = True) -> dict:
    source = HERE / "runs" / campaign
    manifest = load(source / "manifest.json")
    for filename, field in (
        ("benchmark.py", "driver_sha256"),
        ("protocol.md", "protocol_sha256"),
        ("runbook.txt", "runbook_source_sha256"),
    ):
        actual = hashlib.sha256((HERE / filename).read_bytes()).hexdigest()
        if actual != manifest[field]:
            raise ValueError(f"{filename} differs from the source recorded before measurement")
    rows = [r for r in manifest["attempts"] if r["status"] == "success"]
    if {(r["repeat"], r["condition"]) for r in rows} != {
        (r, c) for r in (1, 2, 3) for c in "ABCD"
    } or len(rows) != 12:
        raise ValueError("need exactly three successful runs for every condition")
    prefix = (source / "prefix.txt").read_text(encoding="utf-8")
    if hashlib.sha256(prefix.encode()).hexdigest() != manifest["prefix_sha256"]:
        raise ValueError("prefix hash mismatch")
    workloads = {}
    measurements = 0
    for row in rows:
        folder = HERE / row["path"]
        workload = [
            json.loads(line)
            for line in (folder / "workload.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        reports = list((folder / "measured").glob("*/report.json"))
        if len(workload) != 60 or len(reports) != 1:
            raise ValueError("missing workload or ambiguous result")
        report = load(reports[0])
        requests = [
            json.loads(line)
            for line in reports[0]
            .with_name("requests.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        if len(requests) != 60 or any(not r["ok"] for r in requests):
            raise ValueError("failed or missing request in successful run")
        if any(
            r["token_count_source"] != "server_usage"  # noqa: S105 - provenance, not a credential
            or r["output_tokens"] != 32
            for r in requests
        ):
            raise ValueError("completion count is not the controlled 32 server-reported tokens")
        if any(not math.isfinite(r["ttft_ms"]) or r["ttft_ms"] <= 0 for r in requests):
            raise ValueError("invalid timing")
        timings = sorted(r["ttft_ms"] for r in requests)
        for quantile, field in ((0.5, "ttft_p50_ms"), (0.95, "ttft_p95_ms")):
            position = (len(timings) - 1) * quantile
            left = math.floor(position)
            right = math.ceil(position)
            percentile = timings[left] + (position - left) * (timings[right] - timings[left])
            if not math.isclose(percentile, row[field], rel_tol=1e-8):
                raise ValueError("TTFT percentile does not match raw records")
        start = min(r["send_ts"] for r in requests)
        end = max(r["send_ts"] + r["e2e_ms"] / 1000 for r in requests)
        rate = sum(r["output_tokens"] for r in requests) / (end - start)
        if not math.isclose(rate, row["output_tok_s"], rel_tol=1e-8):
            raise ValueError("throughput does not match raw records")
        if report["target"]["server_flags"]["common"] != manifest["flags"]:
            raise ValueError("serving flags changed")
        if report["plan"]["concurrency_levels"] != [1.0]:
            raise ValueError("concurrency changed")
        workloads[row["repeat"], row["condition"]] = workload
        measurements += len(requests)
    for repeat in (1, 2, 3):
        a, b, c, d = (workloads[repeat, condition] for condition in "ABCD")
        if a != b:
            raise ValueError("A and B payloads differ")
        for i in range(60):
            if a[i]["messages"][0]["content"] != prefix:
                raise ValueError("A prefix changed")
            if len({w[i]["messages"][1]["content"] for w in (a, b, c, d)}) != 1:
                raise ValueError("queries differ across conditions")
            first = c[i]["messages"][0]["content"]
            last = d[i]["messages"][0]["content"]
            if not first.endswith("\n\n" + prefix) or not last.startswith(prefix + "\n\n"):
                raise ValueError("metadata placement violated")
            if first.removesuffix("\n\n" + prefix) != last.removeprefix(prefix + "\n\n"):
                raise ValueError("C and D metadata are not paired")
    result = {
        "campaign": campaign,
        "verified_runs": len(rows),
        "verified_measured_requests": measurements,
        "source_hashes_match": True,
        "paired_workloads_match": True,
        "throughput_recomputed_from_raw_records": True,
        "ttft_percentiles_recomputed_from_raw_records": True,
    }
    if write_result:
        (HERE / "verification.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    args = parser.parse_args()
    if Path(args.campaign).name != args.campaign or args.campaign in (".", ".."):
        parser.error("campaign must be a directory name")
    print(json.dumps(verify(args.campaign), indent=2))
