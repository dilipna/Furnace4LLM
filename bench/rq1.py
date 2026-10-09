"""FurnaceBench RQ1: reconstruction accuracy against hand-written ground truth.

Apps: F1 (support-rag-py, the development fixture, so its scores are optimistic) and
the held-out OSS apps in bench/ground_truth/ (labels committed before the first scan).
Scan = deterministic reconstruction only (the LLM synthesis step is not built, so the
"+LLM" ablation from the plan is not run).

Matching rules (fixed before scoring held-out apps):
- set categories (routes, LLM call sites, models, engines, retrievers, tools, prompts,
  workflows, contradictions): one-to-one matching; P = TP / predicted, R = TP / truth.
  Empty truth and empty prediction scores "n/a" (nothing to find, nothing claimed).
- call sites / retrievers match on file and function (or `also_accept`); a truth
  function of `<module>` matches any prediction in that file.
- prompts match on file::symbol; a predicted message slot (`func#role`) in a file that
  already has a matched prompt is reported as a duplicate, not as TP or FP.
- binary facts (RAG present, dynamic head, existing tests/tracing/timeouts/retries/evals)
  and per-item attributes (retriever store/top_k, tool side effect/approval gate) are
  scored as accuracy.
- calibration: every predicted Claim whose correctness can be decided from the truth
  contributes (confidence, correct) to a reliability table and ECE (5 equal-width bins).

  uv run poe bench-rq1
"""

from __future__ import annotations

import argparse
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from common import EXTERNAL, F1, GROUND_TRUTH, fmt, manifest, md_table, results_dir, write_json
from furnace.contracts.appspec import AppSpec
from furnace.reconstruction.build import reconstruct


def apps() -> list[dict[str, Any]]:
    out = [
        {"app": "support-rag-py (F1)", "split": "dev", "root": F1, "gt": F1 / "ground_truth.yaml"}
    ]
    for gt in sorted(GROUND_TRUTH.glob("*.yaml")):
        spec = yaml.safe_load(gt.read_text(encoding="utf-8"))
        out.append(
            {
                "app": spec["app"],
                "split": spec.get("split", "held-out"),
                "root": EXTERNAL / spec["app"],
                "gt": gt,
            }
        )
    return out


# ------------------------------------------------------------------------- matching


SPLITS = ("dev", "held-out", "held-out-2", "held-out-3")


def _split_key(key: str) -> tuple[str, str]:
    """'component:app/llm.py::stream_answer#llm0' -> ('app/llm.py', 'stream_answer')."""
    body = key.split(":", 1)[1] if ":" in key.split("::", 1)[0] else key
    file, _, rest = body.partition("::")
    return file, re.split(r"[#.]", rest, maxsplit=1)[0] if rest else ""


def _site_match(truth: dict[str, Any], key: str) -> bool:
    file, func = _split_key(key)
    if file != truth["file"]:
        return False
    names = {truth["function"], *truth.get("also_accept", [])}
    return truth["function"] == "<module>" or func in names


def match(
    truth: list[Any], pred: list[Any], eq
) -> tuple[list[tuple[Any, Any]], list[Any], list[Any]]:
    pairs, left = [], list(pred)
    missed = []
    for t in truth:
        hit = next((p for p in left if eq(t, p)), None)
        if hit is None:
            missed.append(t)
        else:
            pairs.append((t, hit))
            left.remove(hit)
    return pairs, missed, left


def prf(tp: int, n_pred: int, n_truth: int) -> dict[str, float | None]:
    p = tp / n_pred if n_pred else None
    r = tp / n_truth if n_truth else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if (p == 0 or r == 0) else None)
    return {"tp": tp, "n_pred": n_pred, "n_truth": n_truth, "precision": p, "recall": r, "f1": f}


def _norm(s: Any) -> str:
    return str(s).strip().lower()


def _model(s: Any) -> str:
    """Model ids compare without a trailing ':<version hash>' (Replicate-style pins)."""
    return re.sub(r":[0-9a-f]{32,}$", "", _norm(s))


# ------------------------------------------------------------------------- scoring


def score(spec: AppSpec, gt: dict[str, Any]) -> dict[str, Any]:
    cats: dict[str, Any] = {}
    attrs: list[dict[str, Any]] = []
    calib: list[tuple[float, bool, str]] = []

    def setcat(name, truth, pred, eq, show: Callable[[Any], str] = str):
        pairs, missed, extra = match(truth, pred, eq)
        cats[name] = {
            **prf(len(pairs), len(pred), len(truth)),
            "missed": [show(m) for m in missed],
            "false_positives": [show(e) for e in extra],
        }
        return pairs

    def attr(name: str, truth: Any, pred: Any, claim=None) -> None:
        ok = _norm(truth) == _norm(pred)
        attrs.append({"attr": name, "truth": truth, "pred": pred, "correct": ok})
        if claim is not None:
            calib.append((claim.confidence, ok, name))

    # routes
    setcat(
        "routes",
        list(gt.get("routes") or []),
        [f"{r.method} {r.path}" for r in spec.routes],
        lambda t, p: _norm(t) == _norm(p),
    )
    # LLM call sites
    pairs = setcat(
        "llm_call_sites",
        list(gt.get("llm_calls") or []),
        spec.llm_calls,
        lambda t, p: _site_match(t, p.key),
        show=lambda x: x.key if hasattr(x, "key") else f"{x['file']}::{x['function']}",
    )
    for t, p in pairs:
        if "streaming" in t and p.streaming is not None:
            attr("call.streaming", t["streaming"], p.streaming.value, p.streaming)
        if "has_timeout" in t:
            attr("call.has_timeout", t["has_timeout"], p.has_timeout)
        if "model" in t:  # per-call model only where the truth names one (null = library default)
            pv = p.model.value if p.model else None
            attr("call.model", t["model"] and _model(t["model"]), pv and _model(pv), p.model)
    # models: app-wide set of model ids claimed anywhere
    truth_models = gt.get("models", [gt["model"]] if gt.get("model") else [])
    pred_models = sorted(
        {_model(c.model.value) for c in spec.llm_calls if c.model and c.model.value}
    )
    setcat("models", [_model(m) for m in truth_models], pred_models, lambda t, p: t == p)
    for c in spec.llm_calls:
        if c.model and c.model.value:
            calib.append(
                (
                    c.model.confidence,
                    _model(c.model.value) in {_model(m) for m in truth_models},
                    "model",
                )
            )
    # serving engines
    eng = gt.get("serving_engine")
    truth_eng = [eng] if isinstance(eng, str) else list(eng or [])
    pred_eng = sorted(
        {_norm(e.engine.value) for e in spec.endpoints if e.engine.value != "unknown"}
        | {
            _norm(c.provider.value)
            for c in spec.llm_calls
            if c.provider and c.provider.value not in (None, "unknown")
        }
    )
    setcat("serving_engines", [_norm(e) for e in truth_eng], pred_eng, lambda t, p: t == p)
    for e in spec.endpoints:
        if e.engine.value != "unknown":
            calib.append(
                (
                    e.engine.confidence,
                    _norm(e.engine.value) in {_norm(x) for x in truth_eng},
                    "engine",
                )
            )
    # RAG
    rag_pred = bool(spec.rag and spec.rag.present.value)
    attr("rag.present", bool(gt.get("uses_rag")), rag_pred, spec.rag.present if spec.rag else None)
    pairs = setcat(
        "retrievers",
        list(gt.get("retrievers") or []),
        spec.rag.retrievers if spec.rag else [],
        lambda t, p: _site_match(t, p.key),
        show=lambda x: x.key if hasattr(x, "key") else f"{x['file']}::{x['function']}",
    )
    for t, p in pairs:
        attr("retriever.store", t["store"], p.store.value, p.store)
        attr("retriever.top_k", t.get("top_k"), p.top_k.value if p.top_k else None, p.top_k)
    # tools
    pairs = setcat(
        "tools",
        list(gt.get("tools") or []),
        spec.tools,
        lambda t, p: _norm(t["name"]) == _norm(p.name),
        show=lambda x: x.name if hasattr(x, "name") else x["name"],
    )
    for t, p in pairs:
        attr("tool.side_effect", t["side_effect"], p.side_effect.value, p.side_effect)
        attr("tool.approval_gate", t["approval_gate"], p.approval_gate.value, p.approval_gate)
    # prompts (slots in an already-matched file are duplicates)
    truth_prompts = list(gt.get("prompts") or [])
    pred_keys = [p.key.split(":", 1)[1] for p in spec.prompts]
    symbols = [k for k in pred_keys if "#" not in k]
    slots = [k for k in pred_keys if "#" in k]
    pairs = setcat("prompts", truth_prompts, symbols, lambda t, p: t == p)
    matched_files = {t.split("::")[0] for t, _ in pairs}
    dups = [s for s in slots if s.split("::")[0] in matched_files]
    extra_slots = [s for s in slots if s not in dups]
    c = cats["prompts"]
    c.update(prf(c["tp"], c["n_pred"] + len(extra_slots), c["n_truth"]))
    c["false_positives"] += extra_slots
    c["duplicates"] = dups
    if "dynamic_head" in gt:
        attr("prompt.dynamic_head", gt["dynamic_head"], any(p.dynamic_head for p in spec.prompts))

    # workflows
    def wf_eq(t: str, p) -> bool:
        if t.startswith(("cli:", "streamlit:")):
            return t.split(":", 1)[1] in p.key
        return _norm(t) == _norm(p.name)

    setcat(
        "workflows",
        list(gt.get("workflows") or []),
        spec.workflows,
        wf_eq,
        show=lambda x: x.key if hasattr(x, "key") else x,
    )
    # existing reliability
    er, rel = gt.get("existing_reliability") or {}, spec.reliability_existing
    pred_rel = {
        "tests": bool(rel.tests),
        "tracing": bool(rel.tracing),
        "timeouts": bool(rel.timeouts) or any(c.has_timeout for c in spec.llm_calls),
        "retries": bool(rel.retries),
        "evals": bool(rel.evals),
    }
    for k, pv in pred_rel.items():
        if k in er:
            tv = er[k] if isinstance(er[k], bool) else _norm(er[k]) not in ("none", "false")
            attr(f"existing.{k}", tv, pv)
    # contradictions
    truth_c = list(gt.get("contradictions") or [])

    def c_eq(t, p) -> bool:
        pv = {_model(v["value"]) for v in p.values}
        return (
            _norm(t["predicate"]) == _norm(p.predicate) and {_model(v) for v in t["values"]} <= pv
        )

    setcat(
        "contradictions",
        truth_c,
        spec.contradictions,
        c_eq,
        show=lambda x: (
            f"{x.predicate}: {[v['value'] for v in x.values]}"
            if hasattr(x, "predicate")
            else f"{x['predicate']}: {x['values']}"
        ),
    )
    return {"categories": cats, "attributes": attrs, "calibration": calib}


def ece(points: list[tuple[float, bool, str]], bins: int = 5) -> dict[str, Any]:
    table = []
    total, err = len(points), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(c, ok) for c, ok, _ in points if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if not sel:
            continue
        conf = sum(c for c, _ in sel) / len(sel)
        acc = sum(ok for _, ok in sel) / len(sel)
        err += len(sel) / total * abs(conf - acc)
        table.append(
            {"bin": f"[{lo:.1f}, {hi:.1f})", "n": len(sel), "mean_conf": conf, "accuracy": acc}
        )
    return {"ece": err if total else None, "n": total, "table": table}


def micro(results: list[dict[str, Any]], split: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sel = [r for r in results if r["split"] == split]
    for cat in sel[0]["score"]["categories"] if sel else []:
        tp = sum(r["score"]["categories"][cat]["tp"] for r in sel)
        npred = sum(r["score"]["categories"][cat]["n_pred"] for r in sel)
        ntruth = sum(r["score"]["categories"][cat]["n_truth"] for r in sel)
        out[cat] = prf(tp, npred, ntruth)
    attrs = [a for r in sel for a in r["score"]["attributes"]]
    empty = [a for r in sel for a in r["empty_scan_attributes"]]
    out["_attributes"] = {
        "correct": sum(a["correct"] for a in attrs),
        "n": len(attrs),
        # What a scanner that finds nothing scores on the same truth (absent facts are "correct").
        "empty_scan_correct": sum(a["correct"] for a in empty),
        "empty_scan_n": len(empty),
    }
    return out


def render(res: dict[str, Any]) -> str:
    lines = [
        "# RQ1: reconstruction accuracy",
        "",
        "Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). "
        "F1 is the development fixture; held-out apps were labeled from source before their first scan "
        "(labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).",
        "",
        "## Micro-averaged P / R / F1",
        "",
    ]
    cats = sorted({c for sp in res["micro"].values() for c in sp} - {"_attributes"})
    order = [
        "routes",
        "llm_call_sites",
        "models",
        "serving_engines",
        "retrievers",
        "tools",
        "prompts",
        "workflows",
        "contradictions",
    ]
    cats = [c for c in order if c in cats]

    def cell(m):
        if m["n_truth"] == 0 and m["n_pred"] == 0:
            return "n/a"
        return f"{fmt(m['precision'], 2)} / {fmt(m['recall'], 2)} / {fmt(m['f1'], 2)} ({m['tp']}/{m['n_pred']}p/{m['n_truth']}t)"

    lines.append(
        md_table(
            ["category", "F1 (dev)", "held-out set 1", "held-out set 2", "held-out set 3"],
            [
                [
                    c,
                    *(
                        cell(res["micro"][sp][c]) if c in res["micro"].get(sp, {}) else "–"
                        for sp in SPLITS
                    ),
                ]
                for c in cats
            ],
            "lllll",
        )
    )
    for split in SPLITS:
        if not res["micro"].get(split, {}).get("_attributes", {}).get("n"):
            continue
        a = res["micro"][split]["_attributes"]
        lines.append(
            f"\nAttribute accuracy ({split}): {a['correct']}/{a['n']} "
            f"(a scan that finds nothing scores {a['empty_scan_correct']}/{a['empty_scan_n']} on the same truth)"
        )
    lines += ["", "## Per app", ""]
    for r in res["apps"]:
        sc = r["score"]
        lines += [f"### {r['app']} ({r['split']}, scan {r['seconds']:.1f}s)", ""]
        lines.append(
            md_table(
                ["category", "P / R / F1 (tp/pred/truth)", "missed", "false positives"],
                [
                    [
                        c,
                        cell(sc["categories"][c]),
                        "; ".join(map(str, sc["categories"][c]["missed"])) or "–",
                        "; ".join(map(str, sc["categories"][c]["false_positives"])) or "–",
                    ]
                    for c in order
                    if c in sc["categories"]
                ],
                "llll",
            )
        )
        wrong = [a for a in sc["attributes"] if not a["correct"]]
        lines.append(
            f"\nAttributes correct: {sum(a['correct'] for a in sc['attributes'])}/{len(sc['attributes'])}"
            + (
                "; wrong: "
                + "; ".join(f"`{a['attr']}` truth={a['truth']!r} pred={a['pred']!r}" for a in wrong)
                if wrong
                else ""
            )
        )
        if sc["categories"]["prompts"].get("duplicates"):
            lines.append(
                f"\nPrompt slot duplicates (not scored): {', '.join(sc['categories']['prompts']['duplicates'])}"
            )
        lines.append("")
    cal = res["calibration"]
    lines += [
        "## Confidence calibration (all apps)",
        "",
        f"ECE = {fmt(cal['ece'], 3)} over n = {cal['n']} decidable claims.",
        "",
    ]
    lines.append(
        md_table(
            ["confidence bin", "n", "mean confidence", "accuracy"],
            [
                [b["bin"], b["n"], fmt(b["mean_conf"], 2), fmt(b["accuracy"], 2)]
                for b in cal["table"]
            ],
        )
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", help="output name suffix, e.g. first_scan -> rq1_first_scan.{json,md}")
    p.add_argument("--splits", help="comma-separated subset of " + ",".join(SPLITS))
    args = p.parse_args()
    results = []
    calib = []
    for a in apps():
        if args.splits and a["split"] not in args.splits.split(","):
            continue
        if not a["root"].exists():
            raise SystemExit(f"{a['root']} missing: run `uv run poe bench-setup` first")
        gt = yaml.safe_load(Path(a["gt"]).read_text(encoding="utf-8"))
        t0 = time.monotonic()
        rec = reconstruct(a["root"])
        secs = time.monotonic() - t0
        sc = score(rec.appspec, gt)
        calib += sc["calibration"]
        results.append(
            {
                "app": a["app"],
                "split": a["split"],
                "commit": gt.get("commit"),
                "seconds": secs,
                "score": {**sc, "calibration": [list(x) for x in sc["calibration"]]},
                "empty_scan_attributes": score(AppSpec(), gt)["attributes"],
                "appspec": rec.appspec.model_dump(mode="json"),
            }
        )
    res = {
        "manifest": manifest(),
        "apps": results,
        "micro": {sp: micro(results, sp) for sp in SPLITS},
        "calibration": ece(calib),
    }
    name = f"rq1_{args.tag}" if args.tag else "rq1"
    out = results_dir()
    write_json(out / f"{name}.json", res)
    (out / f"{name}.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
