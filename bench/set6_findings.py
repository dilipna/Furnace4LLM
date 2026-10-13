"""Held-out set 6: finding correctness of the Blueprint (protocol: docs/scanner-eval-set6.md).

  uv run python bench/set6_findings.py      # FURNACE_BENCH_DATE=2026-10-13-set6

For every app with `split: held-out-6`, runs the product path (reconstruct + run_rules, as a
scan does) and compares the emitted findings with `expected_findings` in its label file.
A finding is (rule, item): item = "app" for app-level rules; for per-item rules, the labeled
item (file + symbol/function + line) is matched by a finding whose node keys name the
symbol/function in that file, or whose evidence span in that file contains the labeled line.
Matching is one-to-one per rule. Rules an app declares in `not_labeled_findings` are left
out of both sides. Precision = matched / emitted; recall = matched / expected, with exact
(Clopper-Pearson) 95% intervals, per rule and pooled. Unmatched findings on either side are
listed for the review that follows the result (never folded into it).

Output: bench/results/<date>/set6/findings.{json,md}
"""

from __future__ import annotations

import uuid
from typing import Any

import yaml
from common import EXTERNAL, GROUND_TRUTH, manifest, md_table, results_dir, write_json
from external_validation import scan as link_check
from furnace.blueprint.rules import run_rules
from furnace.reconstruction.build import reconstruct
from gate_validate import clopper_pearson

PER_ITEM = {
    "sec.tool_approval_boundary",
    "sec.approval_gate_regression_test",
    "obs.prompt_versioning",
    "inf.prefix_instability",
    "inf.prefix_stability_guard",
    "inf.prefix_caching_disabled",
}


def predicted(app_root) -> list[dict[str, Any]]:
    rec = reconstruct(app_root)
    fact_uuid = {f.id: uuid.uuid4() for f in rec.facts.facts}  # as the scan pipeline does
    by_uuid = {v: k for k, v in fact_uuid.items()}
    facts = {f.id: f for f in rec.facts.facts}
    out = []
    for r in run_rules(rec, fact_uuid):
        locs = []
        for e in r.evidence_ids:
            f = facts.get(by_uuid.get(e, ""))
            if f is not None and f.locator.path:
                locs.append((f.locator.path, f.locator.line_start, f.locator.line_end))
        out.append(
            {"rule": r.rule_id, "title": r.title, "node_keys": list(r.node_keys), "locs": locs}
        )
    return out


def item_matches(item: dict[str, Any], p: dict[str, Any]) -> bool:
    file = item["file"]
    name = item.get("symbol") or item.get("function") or ""
    short = name.split(".")[-1]
    for k in p["node_keys"]:
        body = k.split(":", 1)[1] if ":" in k.split("::", 1)[0] else k
        kfile, _, rest = body.partition("::")
        if kfile == file and short and short in rest:
            return True
    line = item.get("line")
    for path, lo, hi in p["locs"]:
        if path == file and line is not None and lo is not None and lo <= line <= (hi or lo):
            return True
    return False


def score_app(gt: dict[str, Any], preds: list[dict[str, Any]]) -> dict[str, Any]:
    skip = set(gt.get("not_labeled_findings") or [])
    expected = [e for e in gt.get("expected_findings") or [] if e["rule"] not in skip]
    emitted = [p for p in preds if p["rule"] not in skip]
    left = list(emitted)
    matched, missed = [], []
    for e in expected:
        cands = [p for p in left if p["rule"] == e["rule"]]
        if e["rule"] in PER_ITEM and isinstance(e["item"], dict):
            hit = next((p for p in cands if item_matches(e["item"], p)), None)
        else:
            hit = cands[0] if cands else None
        if hit is None:
            missed.append(e)
        else:
            matched.append((e, hit))
            left.remove(hit)
    return {
        "expected": len(expected),
        "emitted": len(emitted),
        "matched": len(matched),
        "matched_items": [{"expected": e, "emitted": p["title"]} for e, p in matched],
        "missed": missed,
        "unexpected": [
            {"rule": p["rule"], "title": p["title"], "node_keys": p["node_keys"]} for p in left
        ],
        "excluded_rules": sorted(skip),
        "excluded_emitted": [p["rule"] for p in preds if p["rule"] in skip],
    }


def _pr(m: int, emitted: int, expected: int) -> dict[str, Any]:
    p = m / emitted if emitted else None
    r = m / expected if expected else None
    return {
        "matched": m,
        "emitted": emitted,
        "expected": expected,
        "precision": p,
        "precision_ci95": clopper_pearson(m, emitted) if emitted else None,
        "recall": r,
        "recall_ci95": clopper_pearson(m, expected) if expected else None,
    }


def main() -> None:
    apps = []
    for f in sorted(GROUND_TRUTH.glob("*.yaml")):
        gt = yaml.safe_load(f.read_text(encoding="utf-8"))
        if gt.get("split") == "held-out-6":
            apps.append(gt)
    per_app, by_rule = {}, {}
    for gt in apps:
        res = score_app(gt, predicted(EXTERNAL / gt["app"]))
        per_app[gt["app"]] = res
        for x in res["matched_items"]:
            t = by_rule.setdefault(x["expected"]["rule"], [0, 0, 0])  # matched, emitted, expected
            t[0] += 1
            t[1] += 1
            t[2] += 1
        for e in res["missed"]:
            by_rule.setdefault(e["rule"], [0, 0, 0])[2] += 1
        for u in res["unexpected"]:
            by_rule.setdefault(u["rule"], [0, 0, 0])[1] += 1
    pooled = _pr(
        sum(r["matched"] for r in per_app.values()),
        sum(r["emitted"] for r in per_app.values()),
        sum(r["expected"] for r in per_app.values()),
    )
    rules = {k: _pr(*v) for k, v in sorted(by_rule.items())}

    def pct(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.0%}"

    def ci(c: Any) -> str:
        return "" if not c else f" ({c[0]:.0%}-{c[1]:.0%})"

    text = [
        "# Held-out set 6: finding correctness (pre-registered labels, frozen scanner 41ca529)",
        "",
        "Findings emitted by the product path (reconstruct + Blueprint rules) compared with the "
        "expected findings written from source before the first scan. Precision = emitted findings "
        "that were expected; recall = expected findings that were emitted. Exact 95% intervals. "
        "Labels by the developer agent, not independent. Citation validity and call-site "
        "detection are reported separately (`citations.md`, `rq1`).",
        "",
        md_table(
            ["app", "expected", "emitted", "matched", "precision", "recall", "excluded rules"],
            [
                [
                    a,
                    r["expected"],
                    r["emitted"],
                    r["matched"],
                    pct(r["matched"] / r["emitted"]) if r["emitted"] else "n/a",
                    pct(r["matched"] / r["expected"]) if r["expected"] else "n/a",
                    len(r["excluded_rules"]),
                ]
                for a, r in per_app.items()
            ],
        ),
        "",
        f"**Pooled:** precision {pooled['matched']}/{pooled['emitted']} = {pct(pooled['precision'])}"
        f"{ci(pooled['precision_ci95'])}; recall {pooled['matched']}/{pooled['expected']} = "
        f"{pct(pooled['recall'])}{ci(pooled['recall_ci95'])}.",
        "",
        "## By rule",
        "",
        md_table(
            ["rule", "expected", "emitted", "matched", "precision", "recall"],
            [
                [
                    k,
                    v["expected"],
                    v["emitted"],
                    v["matched"],
                    pct(v["precision"]),
                    pct(v["recall"]),
                ]
                for k, v in rules.items()
            ],
        ),
        "",
        "## Disagreements (for the review; the numbers above stand as computed)",
        "",
    ]
    for a, r in per_app.items():
        for e in r["missed"]:
            text.append(f"- {a}: expected, not emitted: `{e['rule']}` {e['item']}")
        for u in r["unexpected"]:
            text.append(
                f"- {a}: emitted, not expected: `{u['rule']}` ({u['title']}; {u['node_keys'][:3]})"
            )
    # Citation validity: the unchanged evidence-link check of bench/external_validation.py.
    cites = {gt["app"]: link_check(EXTERNAL / gt["app"])[2] for gt in apps}
    n_chk = sum(c["evidence_checked"] for c in cites.values())
    n_bad = sum(len(c["evidence_broken"]) for c in cites.values())
    n_file = sum(c["evidence_file_level"] for c in cites.values())
    ctext = [
        "# Held-out set 6: citation validity (evidence links), reported on its own",
        "",
        "Every evidence item of every Blueprint finding: the cited file exists and, for line-ranged "
        "evidence, the range is inside it and contains the scanner's own excerpt (check unchanged "
        "from `bench/external_validation.py`). This is consistency of the links, not correctness "
        "of the finding.",
        "",
        md_table(
            ["app", "findings", "evidence items checked", "file-level only", "broken"],
            [
                [
                    a,
                    c["findings"],
                    c["evidence_checked"],
                    c["evidence_file_level"],
                    len(c["evidence_broken"]),
                ]
                for a, c in cites.items()
            ],
        ),
        "",
        f"**Pooled:** {n_chk - n_bad}/{n_chk} evidence items resolve ({n_file} of them file-level, "
        "checked for existence only).",
        *[f"- {a}: {b}" for a, c in cites.items() for b in c["evidence_broken"]],
    ]
    out = results_dir("set6")
    write_json(out / "citations.json", {"manifest": manifest(), "apps": cites})
    (out / "citations.md").write_text("\n".join(ctext) + "\n", encoding="utf-8")
    write_json(
        out / "findings.json",
        {"manifest": manifest(), "per_app": per_app, "by_rule": rules, "pooled": pooled},
    )
    (out / "findings.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
