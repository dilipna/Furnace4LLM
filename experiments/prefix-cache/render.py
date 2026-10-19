"""Render only recorded observations. Requires matplotlib; never performs inference."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = {
    "A": "Stable, cache on",
    "B": "Stable, cache off",
    "C": "Metadata first",
    "D": "Metadata last",
}


def summary(attempts: list[dict]) -> dict:
    selected = {}
    for row in attempts:
        if row["status"] == "success":
            key = (row["repeat"], row["condition"])
            if key in selected:
                raise ValueError(f"multiple successful attempts for {key}")
            if row["n_ok"] != 60:
                raise ValueError("incomplete requests cannot enter the summary")
            selected[key] = row
    result = {}
    for condition in LABELS:
        rows = [r for (_, c), r in sorted(selected.items()) if c == condition]
        if len(rows) != 3:
            raise ValueError(f"{condition} has {len(rows)}/3 successful runs; campaign incomplete")
        cache = [r["cache"] for r in rows]
        usable = all(r.get("hits") is not None and r.get("queries") is not None for r in cache)
        denominator = sum(r["queries"] for r in cache) if usable else 0
        log_values = [v for row in rows for v in row.get("logged_cache_percentages", [])]
        result[condition] = {
            "runs": rows,
            "p50": statistics.median(r["ttft_p50_ms"] for r in rows),
            "p95": statistics.median(r["ttft_p95_ms"] for r in rows),
            "tok_s": statistics.median(r["output_tok_s"] for r in rows),
            "cache_rate": sum(r["hits"] for r in cache) / denominator if denominator else None,
            "log_values": log_values,
        }
    return result


def percent(value):
    return "Not exposed / no queries" if value is None else f"{value * 100:.2f}%"


def table(data: dict) -> str:
    rows = [
        "| Condition | TTFT p50 (ms) | TTFT p95 (ms) | Completion tok/s | Cache hit (metrics delta) |",
        "|---|---:|---:|---:|---|",
    ]
    for condition, values in data.items():
        cache_text = (
            "N/A (disabled)"
            if condition == "B" and values["cache_rate"] is None
            else percent(values["cache_rate"])
        )
        rows.append(
            f"| {condition}: {LABELS[condition]} | {values['p50']:.2f} | {values['p95']:.2f} | {values['tok_s']:.2f} | {cache_text} |"
        )
    return "\n".join(rows)


def render(campaign: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    source = HERE / "runs" / campaign
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    data = summary(manifest["attempts"])
    for attempt in manifest["attempts"]:
        folder = HERE / attempt["path"]
        log = folder / "server.log"
        if log.exists():
            runtime_lines = [
                line
                for line in log.read_text(encoding="utf-8").splitlines()
                if any(
                    term in line
                    for term in (
                        "Available KV cache memory",
                        "GPU KV cache size",
                        "Pinned memory",
                        "JIT compilation during inference",
                    )
                )
            ]
            (folder / "runtime-excerpt.txt").write_text(
                "\n".join(runtime_lines) + "\n", encoding="utf-8"
            )
            excerpt = [
                line
                for line in log.read_text(encoding="utf-8").splitlines()
                if "cache hit rate" in line.lower()
            ]
            (folder / "cache-log-excerpt.txt").write_text(
                "\n".join(excerpt) + "\n"
                if excerpt
                else "Cache hit statistics were not visible in the recorded server log.\n",
                encoding="utf-8",
            )
            if attempt["status"] != "success":
                diagnostics = [
                    line
                    for line in log.read_text(encoding="utf-8").splitlines()
                    if "ERROR" in line or "Error:" in line
                ]
                (folder / "diagnostic-excerpt.txt").write_text(
                    "\n".join(diagnostics) + "\n", encoding="utf-8"
                )
    fig, axes = plt.subplots(2, 1, figsize=(10, 8.5), layout="constrained")
    colors = ["#276A9D", "#E39D32"]
    for j, (key, metric) in enumerate((("p50", "ttft_p50_ms"), ("p95", "ttft_p95_ms"))):
        values = [v[key] for v in data.values()]
        lows = [v[key] - min(r[metric] for r in v["runs"]) for v in data.values()]
        highs = [max(r[metric] for r in v["runs"]) - v[key] for v in data.values()]
        positions = [i + (j - 0.5) * 0.35 for i in range(4)]
        bars = axes[0].bar(
            positions,
            values,
            width=0.34,
            label=f"TTFT {key}",
            color=colors[j],
        )
        axes[0].bar_label(bars, fmt="%.1f", padding=5, fontsize=9)
        axes[1].bar(positions, values, width=0.34, color=colors[j], yerr=[lows, highs], capsize=4)
    for ax in axes:
        ax.set_xticks(range(4), [f"{k}\n{v}" for k, v in LABELS.items()])
        ax.set_ylabel("TTFT (ms)")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.18)
        ax.set_axisbelow(True)
    axes[0].set_title("Median run statistics", loc="left")
    axes[1].set_title(
        "Same medians with the full observed run range (different y-axis scale)",
        loc="left",
        fontsize=11,
    )
    axes[0].legend(frameon=False)
    fig.suptitle(
        "Prompt layout and prefix caching\nQwen2.5-0.5B · RTX 3050 Ti 4 GB · concurrency 1",
        weight="bold",
    )
    fig.supxlabel(
        "60 requests/run · 3 runs/condition · bars: median run percentile · whiskers: observed run range",
        fontsize=9,
    )
    fig.savefig(HERE / "ttft-comparison.png", dpi=180)
    plt.close(fig)
    main_table = table(data)
    lines = [
        "# Recorded results: prefix caching and prompt layout",
        "",
        f"Campaign: `{campaign}`. See [protocol](protocol.md) and [manifest](runs/{campaign}/manifest.json).",
        "",
        "All four conditions completed three fresh-server runs with 60 successful measured requests per run (720 total). Warmups are excluded. Main values are medians of the three run-level statistics; requests are not treated as independent repeated experiments.",
        "",
        main_table,
        "",
        "![TTFT comparison](ttft-comparison.png)",
        "",
        "## Every run",
        "",
        "| Repeat | Condition | p50 ms | p95 ms | Completion tok/s | Cache hits / queries (delta) | Logged cache percentages | Evidence |",
        "|---:|---|---:|---:|---:|---|---|---|",
    ]
    for row in manifest["attempts"]:
        link = f"[{row['status']}]({row['path']}/summary.json)"
        if row["status"] != "success":
            lines.append(
                f"| {row['repeat']} | {row['condition']} | — | — | — | — | Failed: {row.get('error', 'unknown')} | {link} |"
            )
            continue
        cache = row["cache"]
        logged = (
            ", ".join(f"{v:g}%" for v in row.get("logged_cache_percentages", []))
            or "Not visible in server logs"
        )
        lines.append(
            f"| {row['repeat']} | {row['condition']} | {row['ttft_p50_ms']:.2f} | {row['ttft_p95_ms']:.2f} | {row['output_tok_s']:.2f} | {cache['hits']} / {cache['queries']} | {logged} | {link} |"
        )
    lines += [
        "",
        "## Metric definitions and scope",
        "",
        "- TTFT: FurnaceBench streaming client, request send to the first chunk carrying generated output; empty/role-only chunks are excluded. Raw records retain first-byte latency separately.",
        "- Completion tok/s: server-reported completion tokens divided by first measured send to last measured completion. Fixed 32-token outputs, ignore EOS. Stream chunks are not counted as tokens.",
        "- Cache hit in the main table: sum of measured-window server counter hit deltas divided by query deltas. Warmup excluded after settling asynchronous counters. Server log percentages are listed separately above; their log windows can include warmup/idle time and are not averaged into a run rate.",
        "- The chart's whiskers show observed run range, not confidence intervals. Stored FurnaceBench request-percentile bootstrap intervals are not used as across-run confidence estimates.",
        "- Single laptop GPU, synthetic runbook and queries, one model, one concurrency, short fixed completions. This establishes no result for Qwen3-4B or production traffic.",
        "",
    ]
    (HERE / "results.md").write_text("\n".join(lines), encoding="utf-8")
    output = {
        k: {name: value for name, value in v.items() if name != "runs"} for k, v in data.items()
    }
    (HERE / "results.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(main_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    args = parser.parse_args()
    if Path(args.campaign).name != args.campaign or args.campaign in (".", ".."):
        parser.error("campaign must be a directory name")
    render(args.campaign)
