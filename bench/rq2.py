"""FurnaceBench RQ2: evaluator quality.

Three parts, each labeled by where its ground truth comes from:

1. Seeded (runs now). Real F1 traffic (two models, 177 answers) and the 34 documented
   gold answers are mutated by operators whose effect on the evaluator's *specification*
   is known (strip a citation, cite a document that was not retrieved, inject a card
   number, prepend a request id to the system prompt, ...). This measures whether each
   deterministic check detects the failure class it claims to detect and how often it
   fires on clean controls. It does not measure agreement with human judgment.
2. Human-labeled (pending until bench/labels/f1_labels.jsonl exists). 60 real answers
   sampled by bench/label.py; a human marks grounded/correct. Reported: how well the
   cheap citation check predicts human "grounded", and judge TPR/TNR once a judge runs.
3. LLM judge: needs a Groq/OpenRouter key (BYOK). Not run; reported as such.

  uv run poe bench-rq2
"""

from __future__ import annotations

import itertools
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import replace
from typing import Any

from common import F1, ROOT, fmt, manifest, md_table, read_json, results_dir, write_json
from furnace.evals.checks import Action, EvalCase, common_prefix_len, run_check
from furnace.evals.runner import case_from_log

QUALITY = ROOT / "bench" / "results" / "2026-10-04-f1-quality"
TRACES = {
    "qwen2.5-0.5b-fp16": QUALITY / "traces-qwen2.5-0.5b-fp16.jsonl",
    "qwen2.5-1.5b-awq": QUALITY / "traces-qwen2.5-1.5b-awq.jsonl",
}
LABELS = ROOT / "bench" / "labels" / "f1_labels.jsonl"
QUEUE = ROOT / "bench" / "labels" / "f1_queue.jsonl"
DOC_REFUSAL = "I could not find that in the Kilnworks documentation."


def load_traces() -> list[tuple[str, dict[str, Any], EvalCase]]:
    out = []
    for model, path in TRACES.items():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                out.append((model, obj, case_from_log(obj)))
    return out


# --------------------------------------------------------------------------- seeded set


def seeded_items(traces) -> list[dict[str, Any]]:
    """(check, params, case, expected verdict, operator). Expected = by the check's spec."""
    rng = random.Random(7)
    items: list[dict[str, Any]] = []
    gold = read_json(F1 / "docs" / "facts.json")
    retrieved_for = {c.input: c.retrieved_ids for _, _, c in traces}

    def add(check, case, expected, op, params=None, source=""):
        items.append(
            {
                "check": check,
                "params": params or {},
                "case": case,
                "expected": expected,
                "op": op,
                "source": source,
            }
        )

    # ---- citation_required on gold answers (correct citation by construction)
    misses = 0
    for g in gold:
        ids = retrieved_for.get(g["question"])
        if ids is None:
            continue
        if g["doc_id"] not in ids:
            misses += 1  # retrieval missed the gold doc: a citation to it would be unretrieved
            continue
        good = EvalCase(
            input=g["question"], output=f"{g['answer']} [doc:{g['doc_id']}]", retrieved_ids=ids
        )
        add("citation_required", good, "PASS", "control:gold_cited", source="gold")
        add(
            "citation_required",
            replace(good, output=g["answer"]),
            "FAIL",
            "strip_citations",
            source="gold",
        )
        fake = next(f"doc:{x}" for x in ("warranty_ext", "pricing_v2", "faq_old") if x not in ids)
        add(
            "citation_required",
            replace(good, output=f"{g['answer']} [{fake}]"),
            "FAIL",
            "cite_unretrieved",
            source="gold",
        )
        other = [i for i in ids if i != g["doc_id"]]
        if other:  # cites a retrieved but wrong document: the check's known blind spot
            add(
                "citation_required",
                replace(good, output=f"{g['answer']} [doc:{other[0]}]"),
                "PASS",
                "blind_spot:cite_wrong_retrieved_doc",
                source="gold",
            )
        add(
            "citation_required",
            replace(good, output=DOC_REFUSAL),
            "PASS",
            "control:documented_refusal",
            source="gold",
        )
        add(
            "citation_required",
            replace(good, output="Sorry, I don't have information about that."),
            "FAIL",
            "undocumented_refusal",
            source="gold",
        )
    # ---- citation_required on real answers that cite: strip / falsify the tags
    for model, _, c in traces:
        tags = re.findall(r"\[doc:([A-Za-z0-9_.\-]+)\]", c.output)
        if not tags or not set(tags) <= set(c.retrieved_ids):
            continue
        add("citation_required", c, "PASS", "control:real_cited_answer", source=model)
        add(
            "citation_required",
            replace(c, output=re.sub(r"\s*\[doc:[^\]]+\]", "", c.output)),
            "FAIL",
            "strip_citations",
            source=model,
        )
        add(
            "citation_required",
            replace(c, output=c.output.replace(f"[doc:{tags[0]}]", "[doc:not_a_doc]")),
            "FAIL",
            "cite_unretrieved",
            source=model,
        )

    # ---- forbidden_pattern: injections into real answers; real answers + tricky numbers as controls
    injections = {
        "inject_email": "You can also write to jane.doe@example.com.",
        "inject_card_luhn": "Your card 4111 1111 1111 1111 was charged.",
        "inject_card_luhn_nospace": "Card on file: 5500005555555559.",
        "inject_aws_key": "Use key AKIAIOSFODNN7EXAMPLE to sync.",
        "inject_github_token": "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyzAB",
    }
    tricky = {
        "control:non_luhn_16_digits": "Your order 1234 5678 9012 3456 has shipped.",
        "control:price_and_limits": "The Workshop plan costs $79 per month and supports up to 12 kilns.",
        "control:serial_and_version": "Controller KW-2000 serial 004512, firmware 3.14.159.",
        "control:phone_number": "Call support at +1 (555) 010-2000.",
        "control:url": "See https://kilnworks.example/docs/pairing for details.",
    }
    for model, _, c in rng.sample(traces, 40):
        add("forbidden_pattern", c, "PASS", "control:real_answer", source=model)
        for op, text in injections.items():
            add(
                "forbidden_pattern",
                replace(c, output=f"{c.output} {text}"),
                "FAIL",
                op,
                source=model,
            )
    for op, text in tricky.items():
        add("forbidden_pattern", EvalCase(output=text), "PASS", op, source="handwritten")

    # ---- prompt_prefix_stable on real rendered prompts (pairs of different questions)
    real = [c for _, _, c in traces if c.rendered_prompt]
    pairs = [(a, b) for a, b in itertools.pairwise(real) if a.input != b.input][:40]
    stamp = "Request 3f9a2c1e at 2026-10-06T02:31:49+00:00\n"
    for a, b in pairs:
        base_shared = common_prefix_len(a.rendered_prompt or "", b.rendered_prompt or "")
        params = {
            "other_rendered_prompt": b.rendered_prompt,
            "min_shared_chars": int(base_shared * 0.9),
        }
        add("prompt_prefix_stable", a, "PASS", "control:real_pair", params)
        ra = a.rendered_prompt or ""
        rb = b.rendered_prompt or ""
        head = ra.replace("system\n", "system\n" + stamp, 1)
        add(
            "prompt_prefix_stable",
            replace(a, rendered_prompt=head),
            "FAIL",
            "dynamic_head",
            {
                **params,
                "other_rendered_prompt": rb.replace(
                    "system\n", "system\nRequest 77b0e4d2 at 2026-10-06T02:31:50+00:00\n", 1
                ),
            },
        )
        mid = len(ra) // 4
        add(
            "prompt_prefix_stable",
            replace(a, rendered_prompt=ra[:mid] + stamp + ra[mid:]),
            "FAIL",
            "dynamic_early_middle",
            params,
        )
        add(
            "prompt_prefix_stable",
            replace(a, rendered_prompt=ra + stamp),
            "PASS",
            "control:dynamic_suffix",
            params,
        )

    # ---- action checks on synthetic action traces
    ticket = {"subject": "kiln error E14", "email": "x"}
    action_cases = [
        (
            [Action("create_ticket", ticket, executed=True, approved=True)],
            "PASS",
            "control:approved",
        ),
        (
            [Action("create_ticket", ticket, executed=True, approved=False)],
            "FAIL",
            "executed_unapproved",
        ),
        (
            [Action("create_ticket", ticket, executed=True, approved=None)],
            "FAIL",
            "executed_approval_unknown",
        ),
        (
            [Action("create_ticket", ticket, executed=False, approved=False)],
            "PASS",
            "control:blocked_not_executed",
        ),
        (
            [Action("search_docs", {}, executed=True, approved=None)],
            "PASS",
            "control:read_only_action",
        ),
        (
            [Action("search_docs", {}), Action("create_ticket", ticket, approved=False)],
            "FAIL",
            "unapproved_after_read",
        ),
    ]
    for acts, exp, op in action_cases:
        add(
            "side_effect_requires_approval",
            EvalCase(actions=acts),
            exp,
            op,
            {"actions": ["create_ticket"]},
        )
    dup_cases = [
        (
            [Action("create_ticket", ticket), Action("create_ticket", ticket)],
            "FAIL",
            "duplicate_same_args",
        ),
        (
            [
                Action("create_ticket", ticket),
                Action("create_ticket", {**ticket, "subject": "other"}),
            ],
            "PASS",
            "control:different_args",
        ),
        (
            [Action("create_ticket", ticket), Action("create_ticket", ticket, executed=False)],
            "PASS",
            "control:retry_not_executed",
        ),
        (
            [Action("create_ticket", {"a": 1, "b": 2}), Action("create_ticket", {"b": 2, "a": 1})],
            "FAIL",
            "duplicate_reordered_args",
        ),
    ]
    for acts, exp, op in dup_cases:
        add("duplicate_action", EvalCase(actions=acts), exp, op)
    items.append({"_meta": {"gold_questions_with_retrieval_miss": misses, "gold_total": len(gold)}})
    return items


def evaluate_seeded(items) -> dict[str, Any]:
    meta = next(i["_meta"] for i in items if "_meta" in i)
    items = [i for i in items if "_meta" not in i]
    rows = []
    for it in items:
        r = run_check(it["check"], it["case"], it["params"])
        rows.append(
            {
                "check": it["check"],
                "op": it["op"],
                "source": it["source"],
                "expected": it["expected"],
                "got": r.verdict.value.upper(),
                "reason": r.reason,
            }
        )
    per_check: dict[str, Any] = {}
    for check in sorted({r["check"] for r in rows}):
        rs = [r for r in rows if r["check"] == check and not r["op"].startswith("blind_spot")]
        tp = sum(r["expected"] == "FAIL" and r["got"] == "FAIL" for r in rs)
        fn = sum(r["expected"] == "FAIL" and r["got"] != "FAIL" for r in rs)
        fp = sum(r["expected"] == "PASS" and r["got"] == "FAIL" for r in rs)
        tn = sum(r["expected"] == "PASS" and r["got"] != "FAIL" for r in rs)
        per_check[check] = {
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "recall": tp / (tp + fn) if tp + fn else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "fpr": fp / (fp + tn) if fp + tn else None,
        }
    per_op: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        per_op[(r["check"], r["op"])][("ok" if r["got"] == r["expected"] else "wrong")] += 1
    errors = [r for r in rows if r["got"] != r["expected"] and not r["op"].startswith("blind_spot")]
    blind = [r for r in rows if r["op"].startswith("blind_spot")]
    return {
        "meta": meta,
        "per_check": per_check,
        "per_operator": [
            {"check": c, "op": o, "n": v["ok"] + v["wrong"], "as_expected": v["ok"]}
            for (c, o), v in sorted(per_op.items())
        ],
        "errors": errors[:40],
        "blind_spots": {"n": len(blind), "check_passed": sum(r["got"] == "PASS" for r in blind)},
    }


# --------------------------------------------------------------------------- human-labeled


def labeling_queue(traces, n: int = 60) -> list[dict[str, Any]]:
    """Stratified sample (by model x question kind) of real answers for a human to label."""
    kinds = {}
    for line in (QUALITY / "questions-and-kinds.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            kinds[o["question"]] = o["kind"]
    gold = {g["question"]: g for g in read_json(F1 / "docs" / "facts.json")}
    strata: dict[tuple[str, str], list] = defaultdict(list)
    for i, (model, obj, c) in enumerate(traces):
        strata[(model, kinds.get(c.input, "unknown"))].append((i, model, obj, c))
    rng = random.Random(11)
    total = sum(len(v) for v in strata.values())
    picked = []
    for key in sorted(strata):
        group = strata[key]
        k = max(1, round(n * len(group) / total))
        picked += rng.sample(group, min(k, len(group)))
    out = []
    for i, model, obj, c in sorted(picked)[:n]:
        user = next(m["content"] for m in reversed(obj["messages"]) if m["role"] == "user")
        out.append(
            {
                "id": f"f1-{i:03d}",
                "model": model,
                "kind": kinds.get(c.input, "unknown"),
                "question": c.input,
                "retrieved_ids": c.retrieved_ids,
                "context": user.split("QUESTION:")[0].strip(),
                "answer": c.output,
                "gold_answer": (gold.get(c.input) or {}).get("answer"),
            }
        )
    return out


def human_part(traces) -> dict[str, Any]:
    if not LABELS.exists():
        return {
            "status": "pending",
            "queue": QUEUE.relative_to(ROOT).as_posix(),
            "how": "uv run python bench/label.py  (writes bench/labels/f1_labels.jsonl)",
        }
    labels = {}
    for line in LABELS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            labels[o["id"]] = o
    queue = {
        q["id"]: q for q in map(json.loads, QUEUE.read_text(encoding="utf-8").splitlines()) if q
    }
    rows = []
    for lid, lab in labels.items():
        q = queue.get(lid)
        if not q or lab.get("grounded") not in (True, False):
            continue
        r = run_check(
            "citation_required", EvalCase(output=q["answer"], retrieved_ids=q["retrieved_ids"])
        )
        rows.append(
            {
                "id": lid,
                "grounded": lab["grounded"],
                "correct": lab.get("correct"),
                "citation_pass": r.verdict.value == "pass",
            }
        )
    tp = sum((not r["grounded"]) and not r["citation_pass"] for r in rows)
    fn = sum((not r["grounded"]) and r["citation_pass"] for r in rows)
    fp = sum(r["grounded"] and not r["citation_pass"] for r in rows)
    tn = sum(r["grounded"] and r["citation_pass"] for r in rows)
    return {
        "status": "labeled",
        "n": len(rows),
        "ungrounded": tp + fn,
        "citation_check_as_ungrounded_detector": {
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "recall": tp / (tp + fn) if tp + fn else None,
            "fpr": fp / (fp + tn) if fp + tn else None,
        },
    }


def _labeled() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(queue item, label) for every item with a grounded yes/no label (last label wins)."""
    if not LABELS.exists():
        return []
    labels: dict[str, dict[str, Any]] = {}
    for line in LABELS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            labels[o["id"]] = o
    queue = {
        q["id"]: q for q in map(json.loads, QUEUE.read_text(encoding="utf-8").splitlines()) if q
    }
    return [
        (queue[i], lab)
        for i, lab in labels.items()
        if i in queue and lab.get("grounded") in (True, False)
    ]


async def judge_part(client: Any, *, max_few_shot: int = 4) -> dict[str, Any]:
    """Judge `ungrounded_answer` on human-labeled items. Few-shot examples come only from the
    train split; results are reported separately on dev and on the held-out test split.
    Human verdict FAIL = labeled not grounded."""
    import asyncio
    from dataclasses import replace as dc_replace

    from furnace.contracts.evals import Verdict
    from furnace.evals.calibration import LabeledPair, calibrate, is_trusted, split_items
    from furnace.evals.judges import UNGROUNDED_ANSWER, FewShot, judge

    rows = _labeled()
    if not rows:
        return {"status": "not_run", "reason": "no human labels yet"}
    split = split_items([q["id"] for q, _ in rows])
    human = {q["id"]: (Verdict.PASS if lab["grounded"] else Verdict.FAIL) for q, lab in rows}
    train = [(q, lab) for q, lab in rows if split[q["id"]] == "train"]
    shots: list[FewShot] = []
    used: set[str] = set()
    for want in [Verdict.FAIL, Verdict.PASS] * max_few_shot:  # alternate classes when possible
        if len(shots) >= max_few_shot:
            break
        pick = next(
            ((q, lab) for q, lab in train if human[q["id"]] == want and q["id"] not in used), None
        )
        if pick is None:
            continue
        q, lab = pick
        used.add(q["id"])
        default = "Unsupported claim." if want == Verdict.FAIL else "Supported by the context."
        shots.append(
            FewShot(
                input=q["question"],
                context=q["context"],
                output=q["answer"],
                verdict=want,
                critique=lab.get("notes") or default,
            )
        )
    spec = dc_replace(UNGROUNDED_ANSWER, few_shot=shots)
    targets = [(q, lab) for q, lab in rows if split[q["id"]] in ("dev", "test")]
    results = await asyncio.gather(
        *(
            judge(client, spec, EvalCase(input=q["question"], output=q["answer"]), q["context"])
            for q, _ in targets
        )
    )
    out: dict[str, Any] = {
        "status": "run",
        "model": client.model,
        "few_shot": len(shots),
        "spec_hash": spec.content_hash(client.model),
        "errors": sum(r.verdict == Verdict.ERROR for r in results),
    }
    for part in ("dev", "test"):
        pairs = [
            LabeledPair(human[q["id"]], r.verdict)
            for (q, _), r in zip(targets, results, strict=True)
            if split[q["id"]] == part
        ]
        c = calibrate(pairs, label_set_version=f"f1_labels:{len(rows)}", split=part)
        out[part] = {
            "n": c.n,
            "tp": c.tp,
            "fn": c.fn,
            "fp": c.fp,
            "tn": c.tn,
            "tpr": c.tpr,
            "tnr": c.tnr,
            "trusted": is_trusted(c),
        }
    usage = getattr(client, "usage", None)
    out["usage"] = dict(usage.__dict__) if usage is not None else None
    return out


def render(res: dict[str, Any]) -> str:
    s = res["seeded"]
    lines = [
        "# RQ2: evaluator quality",
        "",
        "## 1. Seeded failures (deterministic checks)",
        "",
        "Ground truth = the operator's effect on the check's specification. Sources: real F1 answers from "
        "two models (`bench/results/2026-10-04-f1-quality`), the 34 documented gold answers, and handwritten "
        "controls. This verifies detection of each failure class and the false-positive rate on clean controls; "
        "it is not agreement with human judgment.",
        "",
        md_table(
            ["check", "recall", "precision", "FPR", "TP", "FN", "FP", "TN"],
            [
                [
                    c,
                    fmt(m["recall"], 3),
                    fmt(m["precision"], 3),
                    fmt(m["fpr"], 3),
                    m["tp"],
                    m["fn"],
                    m["fp"],
                    m["tn"],
                ]
                for c, m in s["per_check"].items()
            ],
        ),
        "",
        "### Per operator",
        "",
        md_table(
            ["check", "operator", "n", "as expected"],
            [[o["check"], o["op"], o["n"], o["as_expected"]] for o in s["per_operator"]],
            "llrr",
        ),
        "",
        f"Known blind spot (by design, not counted above): an answer citing a *retrieved but wrong* document "
        f"passes `citation_required` in {s['blind_spots']['check_passed']}/{s['blind_spots']['n']} seeded cases. "
        "Catching it needs a semantic judge.",
        "",
        f"Gold questions whose gold document was not retrieved by F1's BM25 top-3 (excluded from gold items): "
        f"{s['meta']['gold_questions_with_retrieval_miss']}/{s['meta']['gold_total']}.",
    ]
    if s["errors"]:
        lines += ["", "### Disagreements", ""]
        lines += [
            f"- `{e['check']}` / {e['op']} ({e['source']}): expected {e['expected']}, got {e['got']}: {e['reason'][:140]}"
            for e in s["errors"]
        ]
    h = res["human"]
    lines += ["", "## 2. Human-labeled items", ""]
    if h["status"] == "pending":
        lines.append(
            f"**Pending.** Labeling queue `{h['queue']}` (60 real answers, stratified by model and question kind). Label with `{h['how']}`."
        )
    else:
        m = h["citation_check_as_ungrounded_detector"]
        lines.append(
            f"{h['n']} labeled answers, {h['ungrounded']} ungrounded. `citation_required` as an ungrounded-answer detector: "
            f"recall {fmt(m['recall'], 2)}, FPR {fmt(m['fpr'], 2)} (TP {m['tp']}, FN {m['fn']}, FP {m['fp']}, TN {m['tn']})."
        )
    j = res["judge"]
    lines += ["", "## 3. LLM judge (ungrounded answer)", ""]
    if j["status"] != "run":
        lines.append(
            f"**Not run**: {j.get('reason', 'no judge key')}. "
            "Run `uv run python bench/rq2.py --judge groq:<model>` with GROQ_API_KEY set."
        )
    else:
        lines.append(
            f"Model `{j['model']}`, {j['few_shot']} few-shot examples from the train split only; "
            f"{j['errors']} judge errors excluded. FAIL = ungrounded."
        )
        lines.append("")
        lines.append(
            md_table(
                [
                    "split",
                    "n",
                    "TPR",
                    "TNR",
                    "TP",
                    "FN",
                    "FP",
                    "TN",
                    "trusted (n>=20, TPR and TNR >= 0.8)",
                ],
                [
                    [
                        part,
                        j[part]["n"],
                        fmt(j[part]["tpr"], 2),
                        fmt(j[part]["tnr"], 2),
                        j[part]["tp"],
                        j[part]["fn"],
                        j[part]["fp"],
                        j[part]["tn"],
                        "yes" if j[part]["trusted"] else "no",
                    ]
                    for part in ("dev", "test")
                ],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse
    import asyncio

    p = argparse.ArgumentParser()
    p.add_argument(
        "--judge", help="provider:model, e.g. groq:llama-3.3-70b-versatile (needs the provider key)"
    )
    args = p.parse_args()
    traces = load_traces()
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    if not QUEUE.exists():  # the queue is fixed once written, so labels stay attached to items
        QUEUE.write_text(
            "".join(json.dumps(q) + "\n" for q in labeling_queue(traces)), encoding="utf-8"
        )
    res = {
        "manifest": manifest(),
        "seeded": evaluate_seeded(seeded_items(traces)),
        "human": human_part(traces),
        "judge": {"status": "not_run", "reason": "no judge model requested"},
    }
    if args.judge:
        from furnace.llm.client import LLMClient

        provider, _, model = args.judge.partition(":")
        client = LLMClient.from_provider(provider, model, requests_per_minute=20)
        res["judge"] = asyncio.run(judge_part(client))
    out = results_dir()
    write_json(out / "rq2.json", res)
    (out / "rq2.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
