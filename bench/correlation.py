"""TTFT versus vLLM queue state on the stored RQ4 runs (no new GPU run).

  uv run python bench/correlation.py

For every RQ4 run (bench/results/2026-10-06/rq4/runs.json: 6 configs x 3 repeats, AC power,
780-830 MHz), each successful request is joined with the vLLM /metrics sample at its send
time (furnace_bench.correlation) and Spearman's rho is computed per concurrency level for
`waiting` (requests queued in vLLM) and `running`. Reported: median rho across the 3 repeats
and its range, the number of requests, and the largest queue seen. Descriptive only:
requests within a run are dependent, so no p-values.

Output: bench/results/<date>/correlation.{json,md}
"""

from __future__ import annotations

import json
import statistics
from typing import Any

from common import RESULTS, ROOT, manifest, md_table, read_json, results_dir, write_json
from furnace_bench.correlation import by_level

RUNS = RESULTS / "2026-10-06" / "rq4" / "runs.json"
FIELDS = ("waiting", "running")


def _jsonl(path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> None:
    index = read_json(RUNS)
    cells: dict[tuple[str, float, str], list[dict[str, Any]]] = {}
    for run in index["runs"]:
        if run.get("launch_failed"):
            continue
        d = ROOT / run["run_dir"]
        reqs, tel = _jsonl(d / "requests.jsonl"), _jsonl(d / "telemetry.jsonl")
        for f in FIELDS:
            for lvl, r in by_level(reqs, tel, f).items():
                cells.setdefault((run["config"], lvl, f), []).append(r)
    out: list[dict[str, Any]] = []
    for (cfg, lvl, f), rs in sorted(cells.items()):
        rhos = [r["rho"] for r in rs if r["rho"] is not None]
        out.append(
            {
                "config": cfg,
                "concurrency": lvl,
                "field": f,
                "repeats": len(rs),
                "repeats_with_rho": len(rhos),
                "rho_median": statistics.median(rhos) if rhos else None,
                "rho_range": [min(rhos), max(rhos)] if rhos else None,
                "requests": sum(r["n"] for r in rs),
                "state_max": max(r["state_max"] for r in rs),
            }
        )
    rec = {(x["config"], x["concurrency"], x["field"]): x for x in out}

    def rho_txt(x: dict[str, Any]) -> str:
        if x["rho_median"] is None:
            return "n/a (constant)"
        lo, hi = x["rho_range"]
        return f"{x['rho_median']:+.2f} ({lo:+.2f} to {hi:+.2f})"

    rows = [
        [
            cfg,
            f"{lvl:g}",
            x["requests"],
            f"{x['state_max']:g}",
            rho_txt(x),
            rho_txt(rec[(cfg, lvl, "running")]),
        ]
        for (cfg, lvl, f), x in sorted(rec.items())
        if f == "waiting"
    ]
    res_dir = results_dir()
    write_json(res_dir / "correlation.json", {"manifest": manifest(source=str(RUNS)), "cells": out})
    text = "\n".join(
        [
            "# TTFT vs vLLM queue state (stored RQ4 runs)",
            "",
            "Each successful request joined with the vLLM /metrics sample at its send time; "
            "Spearman's rho per concurrency level (levels are not pooled: concurrency drives both). "
            "Median across 3 repeats, range in parentheses. Descriptive: requests in a run are "
            "dependent, so no p-values. Source: `bench/results/2026-10-06/rq4/` (AC, 780-830 MHz).",
            "",
            md_table(
                [
                    "config",
                    "concurrency",
                    "requests",
                    "max waiting",
                    "rho(waiting, TTFT)",
                    "rho(running, TTFT)",
                ],
                rows,
            ),
            "",
            "n/a: the state was constant at that level (`waiting` stayed 0: vLLM queued nothing), so "
            "there is nothing to correlate. vLLM queues only when concurrency exceeds max-num-seqs.",
            "",
            "Resolution limit: telemetry is sampled about every 0.3 s while TTFT is tens to hundreds of ms, so "
            "the state 'at send' is the last sample up to ~0.3 s earlier. The negative "
            "rho(running, TTFT) at c >= 8 is consistent with that staleness (a request sent just "
            "after a wave finished sees the earlier, higher count) and is not interpreted further.",
        ]
    )
    (res_dir / "correlation.md").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
