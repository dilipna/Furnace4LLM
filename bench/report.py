"""Assemble bench/results/<date>/REPORT.md from the RQ result files in that directory.

Only numbers present in rq*.json are reported; a missing RQ is listed under "Not run".
Each section links the file it came from.

  uv run poe bench-report
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import ROOT, fmt, manifest, md_table, read_json, results_dir


def load(d: Path, name: str) -> dict[str, Any] | None:
    p = d / name
    return read_json(p) if p.exists() else None


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


RQ1_CATS = (
    "llm_call_sites",
    "models",
    "serving_engines",
    "retrievers",
    "tools",
    "prompts",
    "workflows",
    "contradictions",
)


def rq1_section(d: Path, negatives: list[str]) -> list[str]:
    """Columns: dev fixture; set 1 first scan (frozen, old scanner); set 1 after the fixes it
    motivated (no longer held-out); set 2 with the old scanner; set 2 with the fixed scanner.
    Set 2 was labeled before the fixes, so both set-2 columns are held-out results."""
    first = load(d, "rq1_first_scan.json")
    set2_old = load(d, "rq1_set2_old_scanner.json")
    now = load(d, "rq1.json")
    if not (first or now):
        return ["## RQ1 Reconstruction", "", "Not run in this campaign."]
    cols: list[tuple[str, dict[str, Any] | None, str]] = [
        ("F1 (dev fixture)", now or first, "dev"),
        ("set 1, first scan", first, "held-out"),
        ("set 1 after fixes (not held-out)", now, "held-out"),
        ("set 2, old scanner", set2_old, "held-out-2"),
        ("set 2, fixed scanner", now, "held-out-2"),
    ]
    cols = [c for c in cols if c[1] and c[1]["micro"].get(c[2], {}).get("_attributes", {}).get("n")]
    files = [
        f for f in ("rq1_first_scan.md", "rq1_set2_old_scanner.md", "rq1.md") if (d / f).exists()
    ]
    out = [
        "## RQ1 Reconstruction",
        "",
        "Sources: " + ", ".join(f"`{rel(d / f)}`" for f in files) + ".",
        "",
    ]
    rows = [[cat, *(_prf(r["micro"][sp].get(cat)) for _, r, sp in cols if r)] for cat in RQ1_CATS]
    out.append(
        md_table(
            ["category (P / R (tp/truth))", *(c[0] for c in cols)], rows, "l" * (len(cols) + 1)
        )
    )
    out += [
        "",
        md_table(
            ["attribute accuracy", *(c[0] for c in cols)],
            [
                [
                    "scanner",
                    *(
                        f"{r['micro'][sp]['_attributes']['correct']}/{r['micro'][sp]['_attributes']['n']}"
                        for _, r, sp in cols
                        if r
                    ),
                ],
                [
                    "empty scan (baseline)",
                    *(
                        f"{r['micro'][sp]['_attributes']['empty_scan_correct']}/{r['micro'][sp]['_attributes']['empty_scan_n']}"
                        for _, r, sp in cols
                        if r
                    ),
                ],
            ],
            "l" * (len(cols) + 1),
        ),
    ]
    for label, r in (
        ("first scan (old scanner; dev + set 1)", first),
        ("current scanner (all apps)", now),
    ):
        if r:
            out.append(
                f"\nConfidence ECE, {label}: {fmt(r['calibration']['ece'], 3)} over n = {r['calibration']['n']} decidable claims."
            )
    if first:
        ho = first["micro"]["held-out"]["llm_call_sites"]
        if ho["n_truth"] and (ho["recall"] or 0) < 0.5:
            negatives.append(
                f"**RQ1:** the first scan of held-out set 1 (3 OSS apps) found {ho['tp']}/{ho['n_truth']} LLM call sites. "
                "Probes (minimal files, same scanner) confirmed two causes: SDK calls were extracted inside functions but not at "
                "module level (Streamlit scripts), and LangChain wrappers were not extracted as call sites at all. Both were fixed "
                "afterwards; set 1 is therefore no longer held-out, and set 2 (labeled before the fixes) is the clean test."
            )
    if now and set2_old:
        a, b = set2_old["micro"]["held-out-2"], now["micro"]["held-out-2"]
        if all(a.get(c, {}).get("tp") == b.get(c, {}).get("tp") for c in RQ1_CATS):
            negatives.append(
                "**RQ1 (set 2):** the scanner fixes motivated by set 1 changed nothing on set 2 "
                f"(LLM call sites {b['llm_call_sites']['tp']}/{b['llm_call_sites']['n_truth']} before and after). "
                "Set 2 uses SDKs the scanner has no rules for (Replicate, llama.cpp) and Azure OpenAI behind a "
                "custom base_url: coverage is bounded by hand-written SDK rules, so every unseen SDK is a miss."
            )
        for app in now["apps"]:
            if app["split"] != "held-out-2":
                continue
            sc = app["score"]
            fps = [fp for c in RQ1_CATS for fp in sc["categories"][c]["false_positives"]]
            wrong = [f"{x['attr']}={x['pred']!r}" for x in sc["attributes"] if not x["correct"]]
            if fps or wrong:
                negatives.append(
                    f"**RQ1 (set 2, {app['app']}):** false positives: {'; '.join(map(str, fps)) or 'none'}"
                    + (f"; wrong attributes: {', '.join(wrong)}" if wrong else "")
                    + ". Left unfixed so set 2 stays a clean test."
                )
    if now:
        for sp, label in (("held-out", "set 1 after fixes"), ("held-out-2", "set 2")):
            m = now["micro"].get(sp, {})
            weak = [
                c for c in RQ1_CATS if m.get(c) and m[c]["n_truth"] and (m[c]["recall"] or 0) < 0.5
            ]
            if weak:
                negatives.append(
                    f"**RQ1 ({label}):** recall below 0.5 in: {', '.join(f'{c} ({m[c]["tp"]}/{m[c]["n_truth"]})' for c in weak)}."
                )
    return out


def _prf(m: dict[str, Any] | None) -> str:
    if not m:
        return "–"
    if m["n_truth"] == 0 and m["n_pred"] == 0:
        return "n/a"
    return f"{fmt(m['precision'], 2)} / {fmt(m['recall'], 2)} ({m['tp']}/{m['n_truth']})"


def rq2_section(d: Path, negatives: list[str], not_run: list[str]) -> list[str]:
    r = load(d, "rq2.json")
    if not r:
        return ["## RQ2 Evaluators", "", "Not run in this campaign."]
    s = r["seeded"]
    out = ["## RQ2 Evaluators", "", f"Source: `{rel(d / 'rq2.md')}`.", ""]
    out.append(
        md_table(
            ["check (seeded)", "recall", "FPR", "positives / controls"],
            [
                [
                    c,
                    fmt(m["recall"], 3),
                    fmt(m["fpr"], 3),
                    f"{m['tp'] + m['fn']} / {m['fp'] + m['tn']}",
                ]
                for c, m in s["per_check"].items()
            ],
        )
    )
    out += [
        "",
        "Seeded results verify each check against its own specification; they are expected to be perfect "
        "for deterministic checks and say nothing about agreement with human judgment.",
    ]
    b = s["blind_spots"]
    negatives.append(
        f"**RQ2:** `citation_required` passes answers that cite a retrieved but wrong document "
        f"({b['check_passed']}/{b['n']} seeded cases): it is a format/provenance check, not a groundedness check."
    )
    if r["human"]["status"] == "pending":
        not_run.append(
            "RQ2 human-labeled agreement: queue of 60 real answers is ready (`bench/labels/f1_queue.jsonl`), not labeled yet."
        )
    if r["judge"]["status"] == "not_run":
        not_run.append("RQ2 LLM judge TPR/TNR: no Groq/OpenRouter key configured.")
    return out


def rq3_section(d: Path, negatives: list[str]) -> list[str]:
    r = load(d, "rq3.json")
    if not r:
        return ["## RQ3 Impact-aware selection", "", "Not run in this campaign."]
    s = r["summary"]
    rr = s["regression_recall"]
    out = ["## RQ3 Impact-aware selection", "", f"Source: `{rel(d / 'rq3.md')}`.", ""]
    out.append(
        md_table(
            ["metric", "value"],
            [
                ["scenarios", s["scenarios"]],
                ["suite items executed (targeted)", f"{s['items_executed_pct']:.0f}%"],
                [
                    "wall time full → targeted (s)",
                    f"{s['wall_seconds']['full']:.0f} → {s['wall_seconds']['targeted']:.0f}",
                ],
                [
                    "endpoint-busy time full → targeted (s)",
                    f"{s['endpoint_seconds']['full']:.0f} → {s['endpoint_seconds']['targeted']:.0f}",
                ],
                [
                    "regression recall (full-suite FAILs caught)",
                    f"{rr['caught']}/{rr['total']}"
                    + (f" = {rr['recall']:.2f}" if rr["recall"] is not None else ""),
                ],
                ["warning recall", f"{s['warn_recall']['caught']}/{s['warn_recall']['total']}"],
            ],
            "lr",
        )
    )
    for sc in r["scenarios"]:
        if sc["missed_fail"]:
            negatives.append(
                f"**RQ3:** targeting missed {', '.join(sc['missed_fail'])} on `{sc['scenario']}`."
            )
        if sc["seeded"] and not sc["full_fail"]:
            negatives.append(
                f"**RQ3:** seeded regression `{sc['scenario']}` ({sc['seeded']}) produced no FAIL even in the full suite"
                + (f" (WARN: {', '.join(sc['full_warn'])})" if sc["full_warn"] else "")
                + "; the suite cannot see it on this setup."
            )
    # Floor effect: a citation regression cannot show if the base already fails the contract.
    bases: dict[str, tuple[int, int]] = {}
    for sc in r["scenarios"]:
        c = next((x for x in sc["full"] if x["key"] == "check:citation_required"), None)
        m = re.search(r"vs (\d+)/(\d+) on base", c["detail"]) if c else None
        if m:
            bases[sc["scenario"]] = (int(m.group(1)), int(m.group(2)))
    r3 = bases.get("r3_citation_strip")
    if r3 and r3[0] == 0:
        lo, hi = min(b for b, _ in bases.values()), max(b for b, _ in bases.values())
        # Citation WARN/FAIL on PRs that do not touch prompts or generation = serving nondeterminism.
        noisy = [
            sc["scenario"]
            for sc in r["scenarios"]
            if not set(sc["categories"])
            & {"prompt", "code", "generation_config", "retrieval_config", "model"}
            and any(
                x["key"] == "check:citation_required" and x["verdict"] in ("warn", "fail")
                for x in sc["full"]
            )
        ]
        negatives.append(
            f"**RQ3:** in the R3 run the base revision met the citation contract in 0/{r3[1]} answers, so a "
            "citation regression could not show: a floor effect, not a pass. Across the runs the base rate "
            f"varied from {lo}/{r3[1]} to {hi}/{r3[1]} with identical base code (serving nondeterminism)"
            + (
                f"; the citation check warned on {', '.join(f'`{s}`' for s in noisy)}, which does not change prompts"
                if noisy
                else ""
            )
            + ". The 2026-10-04 live Guard run (`bench/results/2026-10-04-guard`, serving model not recorded "
            "there) had 5/34 on base."
        )
    # Perf-gate noise floor: PRs whose change categories cannot touch the serving path.
    serving = {
        "prompt",
        "retrieval_config",
        "retrieval",
        "serving_config",
        "model",
        "llm_call",
        "endpoint",
        "generation_config",
    }
    noise = []
    for sc in r["scenarios"]:
        if set(sc["categories"]) & serving:
            continue
        b = next((x for x in sc["full"] if x["key"] == "bench:chat_perf_gate"), None)
        m = re.search(r"\(([+-]\d+(?:\.\d+)?)%", b["detail"]) if b else None
        if b and m:
            noise.append((sc["scenario"], float(m.group(1)), b["verdict"]))
    if noise:
        lo, hi = min(n[1] for n in noise), max(n[1] for n in noise)
        out += [
            "",
            f"Perf-gate noise on {len(noise)} PRs that cannot affect serving (full-suite runs): p95 TTFT change "
            f"{lo:+.1f}% to {hi:+.1f}% ("
            + ", ".join(f"`{s}` {v:+.1f}%" for s, v, _ in noise)
            + ").",
        ]
        warns = [s for s, _, v in noise if v == "warn"]
        fails = [s for s, _, v in noise if v == "fail"]
        if warns:
            negatives.append(
                f"**RQ3:** the perf gate's +10% WARN threshold is inside run-to-run noise on this host "
                f"({lo:+.1f}% to {hi:+.1f}% on PRs that cannot affect serving); it warned on "
                f"{', '.join(f'`{s}`' for s in warns)}."
                + (
                    ""
                    if fails
                    else " None of these PRs was blocked: BLOCK also requires separated runs."
                )
            )
        if fails:
            negatives.append(
                f"**RQ3:** the perf gate BLOCKED PRs that cannot affect serving: {', '.join(f'`{s}`' for s in fails)}."
            )
    return out


def rq4_section(d: Path, negatives: list[str]) -> list[str]:
    r = load(d / "rq4", "rq4.json")
    if not r:
        return ["## RQ4 Inference", "", "Not run in this campaign."]
    out = [
        "## RQ4 Inference (laptop GPU)",
        "",
        f"Source: `{rel(d / 'rq4' / 'rq4.md')}` (raw runs in `rq4/runs/`).",
        "",
    ]
    eff = [e for e in r["prefix_effect"] if e["level"] in (8.0, 16.0)]
    out.append(
        md_table(
            [
                "max-num-seqs",
                "c",
                "TTFT p95 change with prefix cache off, median [min, max] %",
                "goodput lost, req/s",
                "pairs",
                "same sign",
            ],
            [
                [
                    e["max_num_seqs"],
                    f"{e['level']:g}",
                    _rng(e["ttft_p95_off_vs_on_pct"]),
                    _rng(e["goodput_on_minus_off_rps"], 2),
                    e["n_pairs"],
                    "yes" if e["consistent_sign"] else "no",
                ]
                for e in eff
            ],
        )
    )
    wl = r["workload"]
    hits = [
        x
        for x in r["rows"]
        if x["config"].startswith("pc-on") and x["prefix_hit_rate"]["median"] is not None
    ]
    if hits:
        lo = min(x["prefix_hit_rate"]["min"] for x in hits) * 100
        hi = max(x["prefix_hit_rate"]["max"] for x in hits) * 100
        out += [
            "",
            f"Prefix-cache hit rate with caching on: {lo:.1f}–{hi:.1f}% measured vs {wl['expected_prefix_hit_rate'] * 100:.1f}% predicted from the workload's shared prefix.",
        ]
    for e in r["prefix_effect"]:
        if not e["consistent_sign"] and e["n_pairs"] > 1:
            negatives.append(
                f"**RQ4:** prefix-cache effect on TTFT p95 at max-num-seqs={e['max_num_seqs']}, c={e['level']:g} is not consistent across repeats ({_rng(e['ttft_p95_off_vs_on_pct'])} %)."
            )
    for f in r["launch_failures"]:
        negatives.append(f"**RQ4:** config {f['config']} repeat {f['repeat']} failed to launch.")
    return out


def _rng(a: dict[str, Any], nd: int = 1) -> str:
    if a["median"] is None:
        return "–"
    return f"{a['median']:+.{nd}f} [{a['min']:+.{nd}f}, {a['max']:+.{nd}f}]"


def _rq5_run(r: dict[str, Any], label: str, negatives: list[str]) -> list[str]:
    r1 = [a for a in r["attempts"] if a["scenario"] == "r1_dynamic_head"]
    ok = sum(a["status"] == "verified" for a in r1)
    rows = []
    for a in r1:
        h, c = a["perf"].get("head_vs_base") or {}, a["perf"].get("candidate_vs_base") or {}
        hit_pair = c.get("prefix_hit_rate") or (None, None)
        h0: float | None = hit_pair[0]
        h1: float | None = hit_pair[1]
        rows.append(
            [
                a["repeat"],
                a["status"],
                f"{h.get('baseline', '–')} → {h.get('value', '–')} ({h.get('change_pct', 0):+.0f}%)",
                f"{c.get('value', '–')} ({c.get('change_pct', 0):+.1f}%, {c.get('verdict', '–')})",
                "–" if h0 is None or h1 is None else f"{h0 * 100:.0f}% → {h1 * 100:.0f}%",
                (a.get("audit") or {}).get("conclusion", "–"),
            ]
        )
    out = [
        md_table(
            [
                "repeat",
                "status",
                "p95 TTFT base → PR, ms",
                "repair p95 TTFT, ms",
                "repair hit rate",
                "full-suite audit",
            ],
            rows,
            "rlllll",
        ),
        "",
        f"{label}: {ok}/{len(r1)} verified; {sum(not (a.get('audit') or {}).get('new_failures') and 'audit' in a for a in r1)}/{len(r1)} audits without a FAIL.",
    ]
    if ok < len(r1):
        negatives.append(
            f"**RQ5 ({label}):** {len(r1) - ok}/{len(r1)} R1 repair attempts were rejected by the gate."
        )
    audits = [a for a in r1 if (a.get("audit") or {}).get("new_failures")]
    if audits:
        negatives.append(
            f"**RQ5 ({label}):** the full-suite audit of the repaired tree failed in {len(audits)}/{len(r1)} repeats "
            f"({', '.join(sorted({f for a in audits for f in a['audit']['new_failures']}))})."
        )
    for a in r1:
        c = a["perf"].get("candidate_vs_base") or {}
        if c.get("verdict") == "warn" and c.get("change_pct", 0) > 25:
            negatives.append(
                f"**RQ5 ({label}):** in repeat {a['repeat']} the gate passed the repair as WARN at "
                f"{c['change_pct']:+.1f}% p95 TTFT because its runs overlapped the base runs; a BLOCK needs "
                "separated runs, so a large but noisy regression can pass."
            )
    return out


def rq5_section(d: Path, negatives: list[str]) -> list[str]:
    r = load(d, "rq5.json")
    v1 = load(d, "rq5_rule_v1.json")
    if not r and not v1:
        return ["## RQ5 Repair", "", "Not run in this campaign."]
    out = ["## RQ5 Repair", ""]
    if r:
        out += [f"Source: `{rel(d / 'rq5.md')}` (current rule strategy).", ""]
        out += _rq5_run(r, "current strategy", negatives)
        for a in r["attempts"]:
            if a["scenario"] != "r1_dynamic_head":
                negatives.append(
                    f"**RQ5:** `{a['scenario']}`: no repair strategy (status `{a['status']}`)."
                )
    if v1:
        out += [
            "",
            f"First run (`{rel(d / 'rq5_rule_v1.md')}`): the rule moved the per-request value to the end of "
            "the *system* message, which still sits before the retrieved context. Kept for the record:",
            "",
        ]
        out += _rq5_run(v1, "first strategy", negatives)
    return out


STATIC_NOT_RUN = [
    "RQ1 F2 (TypeScript agent app): no TypeScript extractor yet.",
    "RQ1 +LLM synthesis ablation: LLM synthesis step not built.",
    "RQ4 Kaggle T4 (Qwen2.5-1.5B fp16 vs AWQ) and Ollama comparison: not run.",
    "RQ4 `vllm bench serve` cross-check: not run.",
    "RQ5 LLM-patch strategy: not built.",
]


def main() -> None:
    d = results_dir()
    negatives: list[str] = []
    not_run: list[str] = []
    body: list[str] = []
    body += [*rq1_section(d, negatives), ""]
    body += [*rq2_section(d, negatives, not_run), ""]
    body += [*rq3_section(d, negatives), ""]
    body += [*rq4_section(d, negatives), ""]
    body += [*rq5_section(d, negatives), ""]
    m = manifest()
    head = [
        f"# FurnaceBench report ({d.name})",
        "",
        f"Generated by `uv run poe bench-report` from the files in `{rel(d)}` at commit `{m['git']['sha']}`"
        + (" (working tree dirty)" if m["git"]["dirty"] else "")
        + f". Hardware: {m.get('gpu', 'no GPU detected')} ({m.get('memory_mb', '?')} MB), driver {m.get('driver', '?')}, {m['platform']}.",
        "Protocols: `docs/furnacebench.md`. Every number below is copied from a results file named in its section.",
        *(
            [f"**Read first:** campaign conditions in `{rel(d / 'NOTES.md')}`."]
            if (d / "NOTES.md").exists()
            else []
        ),
        "",
    ]
    tail = ["## Negative results", ""] + ([f"- {n}" for n in negatives] or ["- none recorded"])
    tail += ["", "## Not run", ""] + [f"- {n}" for n in not_run + STATIC_NOT_RUN]
    tail += [
        "",
        "## Earlier single-run results (2026-10-04, not repeated here)",
        "",
        "- `bench/results/2026-10-04-r1-derisk`: removing a 1,000-token shared prefix, c=16 TTFT p95 752 → 1,577 ms (1 repeat).",
        "- `bench/results/2026-10-04-f1-quality`: citation contract met 3/89 (0.5B) and 9/88 (1.5B AWQ) on real F1 traffic.",
        "- `bench/results/2026-10-04-guard`: live Guard checks for R1-R4 and controls (1 run each).",
    ]
    text = "\n".join(head + body + tail) + "\n"
    (d / "REPORT.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
