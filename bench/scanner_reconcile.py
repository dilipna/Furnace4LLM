"""Scanner metric reconciliation: every figure with its dataset, unit, counts and denominator.

  uv run python bench/scanner_reconcile.py

Reads stored scorer output only (no scan is re-run here); the one fresh input is
`rq1_current_scanner.json`, produced by `bench/rq1.py --tag current_scanner` with
FURNACE_BENCH_DATE=2026-10-12-reconcile. Nothing is re-scored or re-labeled.

Two snapshots per set:
- FIRST SCAN: the scanner as it was the first time that set was scanned, with labels
  committed before. This is the only held-out number a set can ever have.
- CURRENT: today's scanner on the same labels. Every set except the last was used to
  decide scanner changes, so these are development-set numbers, not held-out results.

Output: bench/results/2026-10-12-reconcile/scanner_reconciliation.{json,md}
"""

from __future__ import annotations

import math
from typing import Any

from common import RESULTS, manifest, md_table, read_json, results_dir, write_json

OUT = RESULTS / "2026-10-12-reconcile"

# (set, apps, stored first-scan file, scanner state)
FIRST_SCAN = [
    (
        "set 1",
        "2026-10-06/rq1_first_scan.json",
        "held-out",
        "scanner at 979350b, first scan 2026-10-06",
    ),
    (
        "set 2",
        "2026-10-06/rq1_set2_old_scanner.json",
        "held-out-2",
        "scanner after the set-1 fix, 2026-10-06",
    ),
    (
        "set 3",
        "2026-10-09/rq1_set3_baseline.json",
        "held-out-3",
        "scanner 7fe8c79 (unchanged since labels 129103c)",
    ),
    (
        "set 4",
        "2026-10-11-external/rq1_set4_first_scan.json",
        "held-out-4",
        "scanner unchanged since labels f0fce9d",
    ),
    (
        "set 5",
        "2026-10-11-external/rq1_set5_baseline_before_change.json",
        "held-out-5",
        "scanner unchanged since labels f038d20",
    ),
]
CURRENT = "2026-10-12-reconcile/rq1_current_scanner.json"
CATS = [
    "llm_call_sites",
    "routes",
    "models",
    "serving_engines",
    "retrievers",
    "tools",
    "prompts",
    "workflows",
    "contradictions",
]

GROUND_TRUTH = RESULTS.parent / "ground_truth"


def label_api(app: str, missed: list[str]) -> list[str]:
    """The `api:` string of each missed label, read from the label file (not annotated by hand)."""
    import yaml

    gt = yaml.safe_load((GROUND_TRUTH / f"{app}.yaml").read_text(encoding="utf-8"))
    out = []
    for m in missed:
        file, _, func = m.partition("::")
        for c in gt.get("llm_calls") or []:
            if c["file"] == file and c["function"] == func:
                out.append(str(c.get("api", "?")))
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def counts(micro: dict[str, Any], cat: str) -> dict[str, Any]:
    m = micro.get(cat)
    if not m:
        return {"tp": 0, "pred": 0, "truth": 0}
    return {"tp": m["tp"], "pred": m["n_pred"], "truth": m["n_truth"]}


def pooled(rows: list[dict[str, int]]) -> dict[str, Any]:
    tp = sum(r["tp"] for r in rows)
    pred = sum(r["pred"] for r in rows)
    truth = sum(r["truth"] for r in rows)
    return {
        "tp": tp,
        "fp": pred - tp,
        "fn": truth - tp,
        "pred": pred,
        "truth": truth,
        "precision": tp / pred if pred else None,
        "recall": tp / truth if truth else None,
        "precision_ci95": wilson(tp, pred),
        "recall_ci95": wilson(tp, truth),
    }


def cell(m: dict[str, Any], which: str) -> str:
    v, ci = m[which], m[f"{which}_ci95"]
    den = m["pred"] if which == "precision" else m["truth"]
    if v is None:
        return f"n/a (0/{den})"
    return f"{v:.2f} ({m['tp']}/{den}; 95% CI {ci[0]:.2f}-{ci[1]:.2f})"


def main() -> None:
    first = {}
    for name, f, split, _ in FIRST_SCAN:
        d = read_json(RESULTS / f)
        first[name] = {c: counts(d["micro"][split], c) for c in CATS}
    cur = read_json(RESULTS / CURRENT)
    cur_by_split = {sp: m for sp, m in cur["micro"].items() if m}
    names = {sp: n for n, _, sp, _ in FIRST_SCAN}
    current = {
        names[sp]: {c: counts(m, c) for c in CATS} for sp, m in cur_by_split.items() if sp in names
    }
    dev = {"dev (F1)": {c: counts(cur_by_split["dev"], c) for c in CATS}}

    res: dict[str, Any] = {
        "manifest": manifest(),
        "first_scan": {n: {c: first[n][c] for c in CATS} for n in first},
        "first_scan_pooled": {c: pooled([first[n][c] for n in first]) for c in CATS},
        "current_pooled_sets_1_to_5": {c: pooled([current[n][c] for n in current]) for c in CATS},
        "current": current,
        "dev_fixture_f1": dev,
    }

    ev = RESULTS / "2026-10-11-external" / "external_validation_first_run.json"
    ev_note = ""
    if ev.exists():
        ev_note = str(ev.relative_to(RESULTS))

    L = [
        "# Scanner metrics, reconciled (2026-10-12)",
        "",
        "Every number below is a ratio of counts from stored scorer output. Unit, dataset and denominator are "
        "stated for each. Labels were written by the developer agent from source at pinned commits, "
        "before the first scan of each set; **no label was independently reviewed.**",
        "",
        "## Definitions",
        "",
        "- **Call-site detection** (RQ1 `llm_call_sites`): unit = one labeled LLM call site, identified by "
        "file + function (a label of `<module>` matches any prediction in that file). "
        "TP = a label matched one-to-one by a predicted site; FP = predicted site with no label; "
        "FN = label with no predicted site. Precision = TP/(TP+FP), recall = TP/(TP+FN).",
        "- **Citation accuracy**: unit = one evidence item attached to a Blueprint finding; correct if the cited "
        "file exists and (for line-ranged evidence) the range contains the excerpt. It says nothing about "
        "whether the finding is right or whether a true finding was found "
        f"(`bench/external_validation.py`, stored in `{ev_note}`).",
        "- **Finding detection** (Blueprint recommendations): **not measured.** No labeled set of expected "
        "findings exists for any app, so there is no finding-level TP/FP/FN. Findings are derived from the "
        "call sites, prompts and attributes scored above, so a missed call site also silently removes the "
        "findings that depend on it.",
        "",
        "## 1. Call-site detection, first scan of each set (the held-out figure)",
        "",
    ]
    rows = []
    for n, _, _, state in FIRST_SCAN:
        c = first[n]["llm_call_sites"]
        rows.append(
            [
                n,
                state,
                c["tp"],
                c["pred"] - c["tp"],
                c["truth"] - c["tp"],
                c["pred"],
                c["truth"],
                "n/a" if not c["pred"] else f"{c['tp'] / c['pred']:.2f}",
                f"{c['tp'] / c['truth']:.2f}",
            ]
        )
    p = res["first_scan_pooled"]["llm_call_sites"]
    rows.append(
        [
            "**pooled**",
            "mixed scanner states",
            p["tp"],
            p["fp"],
            p["fn"],
            p["pred"],
            p["truth"],
            f"{p['precision']:.2f}",
            f"{p['recall']:.2f}",
        ]
    )
    L.append(
        md_table(
            [
                "set",
                "scanner state",
                "TP",
                "FP",
                "FN",
                "predicted (TP+FP)",
                "labeled (TP+FN)",
                "precision",
                "recall",
            ],
            rows,
        )
    )
    L += [
        "",
        f"Pooled first-scan recall {cell(p, 'recall')}; precision {cell(p, 'precision')}. "
        "The precision denominator is **4 predicted sites**: sets 1 and 5 produced none, so "
        '"1.00" on first scans rests on four predictions and its 95% lower bound is about 0.51. '
        "The set-4 figure the audit quoted (**2/9 recall**) is row 'set 4': TP 2, FP 0, FN 7 over "
        "3 apps and 9 labeled sites (2 + 6 + 1).",
        "",
        "Missed call sites at first scan, with the API each label names (read from the label files):",
        "",
    ]
    for n, f, sp, _ in FIRST_SCAN:
        d = read_json(RESULTS / f)
        for a in d["apps"]:
            if a["split"] != sp:
                continue
            c = a["score"]["categories"]["llm_call_sites"]
            if c["missed"]:
                apis = sorted(set(label_api(a["app"], c["missed"])))
                L.append(
                    f"- {n}, `{a['app']}`: {len(c['missed'])}/{c['n_truth']} missed; "
                    f"labeled API of the missed sites: {'; '.join(apis)}"
                )
    L += [
        "",
        "Pattern summary (set 4 and 5, the newest): (a) frameworks that hide the SDK call behind an agent "
        "runner (OpenAI Agents SDK `Runner.run*`: 5 of 7 missed sites in set 4, 3 of 3 in set 5), and "
        "(b) clients reached through a container (`clients['openai']`: 2 of 7). Earlier sets: unsupported "
        "SDKs (Replicate, Mistral, Cohere, Bedrock, llama.cpp) and module-level script calls.",
        "",
        "## 2. The same labels, current scanner (development-set numbers, NOT held-out)",
        "",
        "Sets 1-5 were each used to decide a scanner change after their first scan "
        "(commits 261b771, 80cb760, 7a3b431 and later). Scoring today's scanner on them measures how "
        "well the fixes fit those apps. It does not predict performance on a new app.",
        "",
    ]
    cp = res["current_pooled_sets_1_to_5"]["llm_call_sites"]
    L.append(
        md_table(
            ["set", "TP", "FP", "FN", "predicted", "labeled", "precision", "recall"],
            [
                [
                    n,
                    c["llm_call_sites"]["tp"],
                    c["llm_call_sites"]["pred"] - c["llm_call_sites"]["tp"],
                    c["llm_call_sites"]["truth"] - c["llm_call_sites"]["tp"],
                    c["llm_call_sites"]["pred"],
                    c["llm_call_sites"]["truth"],
                    "n/a"
                    if not c["llm_call_sites"]["pred"]
                    else f"{c['llm_call_sites']['tp'] / c['llm_call_sites']['pred']:.2f}",
                    f"{c['llm_call_sites']['tp'] / c['llm_call_sites']['truth']:.2f}",
                ]
                for n, c in current.items()
            ]
            + [
                [
                    "**pooled**",
                    cp["tp"],
                    cp["fp"],
                    cp["fn"],
                    cp["pred"],
                    cp["truth"],
                    f"{cp['precision']:.2f}",
                    f"{cp['recall']:.2f}",
                ]
            ],
        )
    )
    L += [
        "",
        "## 3. Every category, pooled over sets 1-5",
        "",
        'Precision and recall per category (TP, FP, FN, denominators in parentheses). **"Precision 1.00" '
        "holds for call sites and routes only.** Prompts, workflows and contradictions produce false "
        "positives on the current scanner.",
        "",
    ]
    rows = []
    for c in CATS:
        f_, cu = res["first_scan_pooled"][c], res["current_pooled_sets_1_to_5"][c]
        rows.append(
            [
                c,
                f"P {pct(f_['precision'])} ({f_['tp']}/{f_['pred']}), R {pct(f_['recall'])} ({f_['tp']}/{f_['truth']})",
                f"P {pct(cu['precision'])} ({cu['tp']}/{cu['pred']}), R {pct(cu['recall'])} ({cu['tp']}/{cu['truth']})",
            ]
        )
    L.append(md_table(["category", "first scan (held-out)", "current scanner (dev set)"], rows))
    L += [
        "",
        "Notes: `routes` are scored only on sets 2, 4 and 5 (sets 1 and 3 label no routes); no scanner "
        "change touched routes, so first-scan and current agree. The scorer matches prompts by "
        "`file::symbol`; on sets 4 and 5 the scanner reports prompt *files* and per-call system slots "
        "while the labels name Python attributes, so prompt precision there is low partly by labeling "
        "convention (disclosed in `2026-10-11-external/NOTES.md`; the labels were not changed after the scan).",
        "",
        "## 4. Citation accuracy (a different quantity)",
        "",
        "The check covers **every** evidence item of every Blueprint finding (no sampling). "
        "First run on held-out set 4 (3 apps): 11 findings, 10 evidence items, 10 resolved, 0 broken "
        "(`external_validation_first_run.md`; that run did not record how many items were file-level). "
        "Current scanner, same 3 apps (`2026-10-12-reconcile/external_validation.md`): 15 findings, "
        "20 evidence items, 0 broken, of which 1 is file-level evidence that passes on file existence "
        "alone. A line-ranged item passes when the file exists, the range is inside it and the first "
        "60 characters of the scanner's own excerpt appear within one line of the range. So this is "
        "**internal consistency of evidence links**; it is not finding precision (no finding was "
        'judged correct or incorrect) and not finding recall. It is the audit\'s "10/10".',
        "",
        "## 5. What may be claimed",
        "",
        "- Call-site detection on apps the scanner had not seen: recall 4/34 (12%, 95% CI 5-27%), "
        "precision 4/4. Range across sets: 0% to 22%.",
        "- After set-specific fixes, the same 34 labeled sites: recall 33/34, precision 33/33. That is "
        "fit to those apps; the 95% lower bound on precision is 0.90, and it says nothing about unseen apps.",
        '- "1.00 precision" must always carry: call sites only, n predicted = 33 (4 on first scan), '
        "labels by the developer agent, scanner tuned on the same apps.",
        "- Held-out recall has been below 30% on three of the last three first scans (sets 3, 4, 5: "
        "11%, 22%, 0%). Generalization of recall is not established.",
    ]
    out = results_dir()
    write_json(out / "scanner_reconciliation.json", res)
    (out / "scanner_reconciliation.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
