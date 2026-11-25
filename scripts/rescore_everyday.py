"""Score saved outputs without inference or overwriting the original evidence."""

import argparse
import hashlib
import json
from pathlib import Path

from furnace.runtime.scoring import SCORER_VERSION, ScoringRule, score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("records", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    original = root / "apps/api/furnace_api/everyday_suite_v1.json"
    revised = root / "apps/api/furnace_api/everyday_suite.json"
    old_cases = {c["name"]: c for c in json.loads(original.read_text(encoding="utf-8"))["cases"]}
    new_cases = {c["name"]: c for c in json.loads(revised.read_text(encoding="utf-8"))["cases"]}
    result = {
        "schema": "furnace-everyday-rescore-v1",
        "scorer": SCORER_VERSION,
        "inference": False,
        "new_suite_sha256": hashlib.sha256(revised.read_bytes()).hexdigest(),
        "limits": "Saved outputs only. Rule checks are not semantic quality. Old records remain untouched.",
        "records": [],
    }
    for path in args.records:
        raw = path.read_bytes()
        record = json.loads(raw)
        assert record["suite_sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
        entry = {
            "source": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "old_scorer": record["scorer"],
            "cases": [],
        }
        for observed in record["cases"]:
            old, new = old_cases[observed["name"]], new_cases[observed["name"]]
            assert old["request"] == new["request"], "Re-scoring requires identical task inputs"

            def check(case, output):
                rule = ScoringRule.model_validate(case["scoring"]) if case["scoring"] else None
                return score(rule, output, None, case["request"]["text"])[0]

            entry["cases"].append(
                {
                    "name": observed["name"],
                    "revised_rule": new["scoring"],
                    "old": observed["score"],
                    "v3_original_rules": check(old, observed.get("output", "")),
                    "v3_revised_rules": check(new, observed.get("output", "")),
                }
            )
        entry["totals"] = {
            column: {
                status: sum(c[column] == status for c in entry["cases"])
                for status in ("pass", "fail", "unscored")
            }
            for column in ("old", "v3_original_rules", "v3_revised_rules")
        }
        result["records"].append(entry)
    if args.out.exists():
        raise SystemExit("Refusing to overwrite an existing rescore record")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([r["totals"] for r in result["records"]], indent=2))


if __name__ == "__main__":
    main()
