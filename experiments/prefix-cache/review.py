"""CPU-only review of saved measurements. Python standard library; no inference or network."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CAMPAIGN = "2026-10-19-small-model-v2"


def module(name: str):
    spec = importlib.util.spec_from_file_location(f"prefix_{name}", HERE / f"{name}.py")
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def counter(text: str, name: str) -> float:
    """Sum all labelled series, excluding HELP, created and external-cache metrics."""
    pattern = re.compile(rf"^{re.escape(name)}(?:\{{[^\n]*\}})?\s+(\S+)(?:\s+\S+)?$")
    values = [float(m[1]) for line in text.splitlines() if (m := pattern.fullmatch(line))]
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError(f"missing or invalid counter: {name}")
    return sum(values)


def cache_from_snapshots(before: str, after: str) -> dict:
    deltas = {}
    for key in ("hits", "queries"):
        name = f"vllm:prefix_cache_{key}_total"
        deltas[key] = counter(after, name) - counter(before, name)
    if not 0 <= deltas["hits"] <= deltas["queries"]:
        raise ValueError("cache counters reset or hits exceed queries")
    return {**deltas, "rate": deltas["hits"] / deltas["queries"] if deltas["queries"] else None}


def equal(actual, expected, label: str) -> None:
    if actual is None or expected is None:
        same = actual is expected
    else:
        same = math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
    if not same:
        raise ValueError(f"{label} disagrees with saved raw evidence")


def audit(campaign: str) -> dict:
    if Path(campaign).name != campaign or campaign in (".", ".."):
        raise ValueError("campaign must be a directory name")
    checks = module("verify").verify(campaign, write_result=False)
    renderer = module("render")
    manifest = json.loads((HERE / "runs" / campaign / "manifest.json").read_text(encoding="utf-8"))
    for row in manifest["attempts"]:
        folder = (HERE / row["path"]).resolve()
        if not folder.is_relative_to((HERE / "runs" / campaign).resolve()):
            raise ValueError("attempt path leaves the campaign")
        if row["status"] != "success":
            continue
        saved = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        if saved != row:
            raise ValueError("attempt summary differs from manifest")
        cache = cache_from_snapshots(
            (folder / "metrics-before.prom").read_text(encoding="utf-8"),
            (folder / "metrics-after.prom").read_text(encoding="utf-8"),
        )
        for key in ("hits", "queries", "rate"):
            equal(row["cache"][key], cache[key], f"{row['path']} cache {key}")
        report_file = next((folder / "measured").glob("*/report.json"))
        report = json.loads(report_file.read_text(encoding="utf-8"))
        flags = report["target"]["server_flags"]
        if flags["cache"] is not (row["condition"] != "B") or flags["image"] != manifest["image"]:
            raise ValueError("cache toggle or image differs from protocol")
    data = renderer.summary(manifest["attempts"])
    published = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    if set(published) != set(data):
        raise ValueError("published conditions differ")
    for condition, values in data.items():
        for key in ("p50", "p95", "tok_s", "cache_rate"):
            equal(published[condition][key], values[key], f"published {condition} {key}")
        if published[condition]["log_values"] != values["log_values"]:
            raise ValueError("published logged cache percentages differ")
    table = renderer.table(data)
    for path in (HERE / "results.md", HERE / "writeup.md", HERE.parents[1] / "README.md"):
        if table not in path.read_text(encoding="utf-8"):
            raise ValueError(f"published table out of sync in {path.name}")
    checks.update(cache_counters_recomputed=True, published_tables_match=True)
    return {"checks": checks, "manifest": manifest, "data": data, "labels": renderer.LABELS}


def document(result: dict) -> str:
    """A self-contained report: no JavaScript, fonts, CDN, server, or external assets."""
    data, manifest, labels = result["data"], result["manifest"], result["labels"]
    esc = html.escape
    reduction = 100 * (1 - data["D"]["p50"] / data["C"]["p50"])
    rows, bars, runs = [], [], []
    scale = 640 / max(v["p95"] for v in data.values())
    for index, (condition, values) in enumerate(data.items()):
        cache = "N/A (disabled)" if values["cache_rate"] is None else f"{values['cache_rate']:.2%}"
        rows.append(
            f"<tr><th>{condition}: {esc(labels[condition])}</th><td>{values['p50']:.2f}</td><td>{values['p95']:.2f}</td><td>{values['tok_s']:.2f}</td><td>{cache}</td></tr>"
        )
        y = index * 80 + 20
        bars.append(f'<text x="0" y="{y + 15}">{condition}</text>')
        for key, offset, color in (("p50", 0, "#60c2ff"), ("p95", 27, "#f9b95d")):
            bars.append(
                f'<rect x="35" y="{y + offset}" width="{values[key] * scale:.2f}" height="21" rx="3" fill="{color}"/><text x="{45 + values[key] * scale:.2f}" y="{y + offset + 16}">{values[key]:.2f} ms</text>'
            )
        for row in values["runs"]:
            runs.append(
                f"<tr><th>{condition} / {row['repeat']}</th><td>{row['ttft_p50_ms']:.2f}</td><td>{row['ttft_p95_ms']:.2f}</td><td>{row['output_tok_s']:.2f}</td></tr>"
            )
    failed = [r for r in manifest["attempts"] if r["status"] != "success"]
    failures = "".join(f"<li>{esc(r['path'])}: {esc(r['status'])}</li>" for r in failed)
    flags = esc(" ".join(manifest["flags"]))
    checks = "".join(
        f"<li>{esc(key.replace('_', ' '))}: {esc(str(value))}</li>"
        for key, value in result["checks"].items()
    )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Furnace — prefix-cache evidence review</title>
<style>
:root{{color-scheme:dark;font-family:system-ui,sans-serif;background:#0b1220;color:#e5edf7}}
body{{max-width:1000px;margin:auto;padding:36px 24px;line-height:1.6}}a{{color:#60c2ff}}
h1{{font-size:clamp(2rem,5vw,3rem);line-height:1.15;margin:12px 0}}h2{{margin-top:32px}}
.eyebrow{{color:#60c2ff;letter-spacing:.12em;font-size:.8rem}}.lead{{font-size:1.15rem;max-width:760px}}
.panel{{background:#131e30;border:1px solid #2c3d56;border-radius:12px;padding:20px;margin:22px 0}}
.muted,small{{color:#afbdd1}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}
th,td{{padding:11px;text-align:right;border-bottom:1px solid #2c3d56;white-space:nowrap}}th:first-child{{text-align:left}}
svg{{width:100%;height:auto}}svg text{{fill:#e5edf7;font:15px system-ui,sans-serif}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#080e19;padding:16px;border-radius:8px}}code{{font-size:.9rem}}
summary{{cursor:pointer;font-weight:600}}.badge{{display:inline-block;color:#a7f3ce;background:#12352b;padding:5px 12px;border-radius:20px}}
@media print{{:root{{color-scheme:light;background:white;color:black}}.panel,pre{{background:white;color:black}}svg text{{fill:black}}.muted,small{{color:#444}}}}
</style>
<header><div class="eyebrow">FURNACE / MEASURED INFERENCE BEHAVIOR</div>
<h1>Request metadata can erase prefix-cache reuse.</h1>
<p class="lead">Moving identical request-specific metadata after a shared runbook recorded <strong>{reduction:.1f}% lower median run p50 TTFT</strong> on this laptop workload.</p>
<span class="badge">Saved evidence passed consistency checks</span>
<p class="muted">{esc(manifest["model"])} · RTX 3050 Ti, 4 GB · concurrency 1 · 12 runs · 720 measured requests</p></header>
<section class="panel"><h2 style="margin-top:0">The change</h2>
<pre><code>Before: [unique session + timestamp] [shared 1500-token runbook]
After:  [shared 1500-token runbook] [same session + timestamp]</code></pre>
<p>Three fresh-server repeats per condition, 60 queries per run, four excluded warmups per run and fixed 32-token completions. All measured requests succeeded.</p></section>
<h2>Median run statistics</h2><p><span style="color:#60c2ff">■ p50 TTFT</span> &nbsp; <span style="color:#f9b95d">■ p95 TTFT</span></p>
<svg viewBox="0 0 800 345" role="img" aria-labelledby="chart-title"><title id="chart-title">Measured time to first token by condition. Exact values follow in the table.</title>{"".join(bars)}</svg>
<div class="scroll"><table><thead><tr><th>Condition</th><th>p50 TTFT (ms)</th><th>p95 TTFT (ms)</th><th>Output tok/s</th><th>Cached tokens</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="muted">Medians of three run-level statistics, not pooled request percentiles. Cache reuse is summed measured-window token hits / token queries. It is not a request hit rate. This chart shows medians; every run, including tail outliers, appears below.</p>
<section class="panel"><h2 style="margin-top:0">What this establishes</h2>
<p>For this controlled workload, prefix layout changed cached-token reuse and streamed latency. The same FurnaceBench streaming client measures every condition. The mitigation preserved the paired metadata and queries.</p>
<p><strong>Limits:</strong> one small model, one laptop GPU, synthetic inputs, concurrency one, short fixed outputs. No answer-quality evaluation, customer adoption, production speed guarantee, or Qwen3-4B result. A cache-off run reached 3072.90 ms p95; no outliers were removed. Consistency checks are not independent authentication of where measurements originated.</p></section>
<details open><summary>Every successful run — variability retained</summary><div class="scroll"><table><thead><tr><th>Condition / repeat</th><th>p50 TTFT (ms)</th><th>p95 TTFT (ms)</th><th>Output tok/s</th></tr></thead><tbody>{"".join(runs)}</tbody></table></div></details>
<h2>Failures remain part of the record</h2><ul>{failures}</ul>
<p>The failed CUDA startup was retried with identical flags. An earlier campaign stopped before measurement when its runbook was too short; it remains in the repository. Neither failure contributes performance values.</p>
<details><summary>Verification and exact serving flags</summary><ul>{checks}</ul><pre><code>{flags}</code></pre><p>A/C/D: --enable-prefix-caching. B: --no-enable-prefix-caching.</p><p>Model revision: <code>{esc(manifest["model_revision"])}</code></p><p>Image: <code>{esc(manifest["image"])}</code></p></details>
<h2>Inspect or reproduce</h2><pre><code>python experiments/prefix-cache/review.py
# Rerun inference only with the documented GPU prerequisites:
bash experiments/prefix-cache/run.sh my-campaign</code></pre>
<p><a href="writeup.md">Technical write-up</a> · <a href="results.md">Results and raw evidence links</a> · <a href="protocol.md">Frozen protocol</a> · <a href="README.md">Reproduction instructions</a></p>
<footer class="muted">Independent project by Dilip Nallamasa. Generated from saved measurements; opening this file does not run inference or contact any service.</footer></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default=DEFAULT_CAMPAIGN)
    parser.add_argument("--html", type=Path, help="write a portable HTML report after verification")
    args = parser.parse_args()
    try:
        result = audit(args.campaign)
        if args.html:
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(document(result), encoding="utf-8")
    except (ValueError, KeyError, OSError, StopIteration, TypeError) as exc:
        print(f"EVIDENCE CHECK FAILED: {exc}")
        return 1
    print(json.dumps(result["checks"], indent=2))
    print("PASS: saved measurements and published tables agree. No inference performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
