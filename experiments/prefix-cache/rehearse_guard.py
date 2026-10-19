"""Run Furnace Forge's actual prefix test on saved prompts, without a model or GPU."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMPAIGN = "2026-10-19-small-model-v2"
TEMPLATE_PATH = ROOT / "packages/furnace/src/furnace/forge/templates.py"

HARNESS = '''"""Replay saved synthetic messages; never calls a model or imports an application."""
import json
from pathlib import Path

ROWS = json.loads(Path(__file__).with_name("messages.json").read_text(encoding="utf-8"))
MESSAGES = {row["question"]: row["messages"] for row in ROWS}

def render(question):
    return MESSAGES[question]
'''

# The actual generated test computes the prefix. This footer reports its observation
# and exit status without changing that test's assertions or threshold semantics.
FOOTER = """
if __name__ == "__main__":
    import json
    import sys
    first = _text(QUESTIONS[0])
    shared = min(_shared(first, _text(q)) for q in QUESTIONS[1:])
    try:
        test_prompt_prefix_is_shared_across_requests()
    except AssertionError:
        print(json.dumps({"status": "FAIL", "shared_chars": shared, "required_chars": MIN_SHARED_CHARS}))
        sys.exit(1)
    print(json.dumps({"status": "PASS", "shared_chars": shared, "required_chars": MIN_SHARED_CHARS}))
"""


def template() -> str:
    """Read the literal shipped by Forge, without importing the application stack."""
    tree = ast.parse(TEMPLATE_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PREFIX_TEST" for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                break
            return value
    raise ValueError("Forge PREFIX_TEST literal was not found")


def load_workload(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) < 2:
        raise ValueError("need at least two distinct saved questions")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("messages"), list):
            raise ValueError("each JSONL row must contain a messages array")
        messages = row["messages"]
        if not messages or any(
            not isinstance(m, dict)
            or not isinstance(m.get("role"), str)
            or not isinstance(m.get("content"), str)
            for m in messages
        ):
            raise ValueError("only text messages are supported")
        if messages[-1]["role"] != "user":
            raise ValueError("expected a final user question")
        result.append({"question": messages[-1]["content"], "messages": messages})
    if len({row["question"] for row in result}) != len(result):
        raise ValueError("duplicate questions would make the replay ambiguous")
    return result


def run_test(rows: list[dict], shared: int, threshold: int, source: str) -> dict:
    questions = [row["question"] for row in rows]
    generated = source
    for key, value in {
        "SHARED": shared,
        "THRESHOLD": threshold,
        "QUESTIONS": repr(questions),
    }.items():
        generated = generated.replace(f"__{key}__", str(value))
    with tempfile.TemporaryDirectory(prefix="furnace-prefix-replay-") as directory:
        folder = Path(directory)
        (folder / "messages.json").write_text(json.dumps(rows), encoding="utf-8")
        (folder / "furnace_harness.py").write_text(HARNESS, encoding="utf-8")
        test = folder / "test_prompt_prefix.py"
        test.write_text(generated + FOOTER, encoding="utf-8")
        process = subprocess.run(  # noqa: S603 - fixed interpreter and trusted Forge template
            [sys.executable, "-E", "-S", str(test)],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if process.returncode not in (0, 1):
        raise ValueError("generated prefix test did not complete")
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("generated test produced no valid result") from exc
    if result["status"] != ("PASS" if process.returncode == 0 else "FAIL"):
        raise ValueError("test status and process exit code disagree")
    return {**result, "exit_code": process.returncode}


def compare(base_rows: list[dict], head_rows: list[dict], source: str) -> dict:
    if [r["question"] for r in base_rows] != [r["question"] for r in head_rows]:
        raise ValueError("base and head must contain identical questions in identical order")
    base = run_test(base_rows, 0, 0, source)["shared_chars"]
    threshold = int(base * 0.9)
    role_prefix = len(base_rows[0]["messages"][0]["role"]) + 1
    if threshold <= role_prefix:
        raise ValueError("baseline has no meaningful shared text prefix to protect")
    return {"base_shared_chars": base, **run_test(head_rows, base, threshold, source)}


def rehearse() -> dict:
    source = template()
    manifest = json.loads((HERE / "runs" / CAMPAIGN / "manifest.json").read_text(encoding="utf-8"))
    rows = [row for row in manifest["attempts"] if row["status"] == "success"]
    expected_pairs = {(repeat, condition) for repeat in (1, 2, 3) for condition in "ABCD"}
    if len(rows) != 12 or {(r["repeat"], r["condition"]) for r in rows} != expected_pairs:
        raise ValueError("expected exactly three successful runs per condition")
    results = []
    for repeat in (1, 2, 3):
        selected = {r["condition"]: r for r in rows if r["repeat"] == repeat}
        workloads = {
            key: load_workload(HERE / row["path"] / "workload.jsonl")
            for key, row in selected.items()
        }
        for condition in "ABCD":
            actual = compare(workloads["A"], workloads[condition], source)
            expected = "FAIL" if condition == "C" else "PASS"
            results.append(
                {"repeat": repeat, "condition": condition, "expected": expected, **actual}
            )
    return {
        "kind": "offline structural replay, not a latency measurement",
        "campaign": CAMPAIGN,
        "template": TEMPLATE_PATH.relative_to(ROOT).as_posix(),
        "template_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "all_expected_outcomes": all(r["status"] == r["expected"] for r in results),
        "results": results,
        "boundary": "B passes structurally despite disabled caching; this test does not measure latency or actual KV cache reuse.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="save replay observations")
    parser.add_argument("--base", type=Path, help="base revision's rendered JSONL workload")
    parser.add_argument("--head", type=Path, help="candidate revision's matching JSONL workload")
    args = parser.parse_args()
    if bool(args.base) != bool(args.head):
        parser.error("--base and --head must be provided together")
    try:
        result = (
            compare(load_workload(args.base), load_workload(args.head), template())
            if args.base and args.head
            else rehearse()
        )
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"REHEARSAL ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.base:
        print(json.dumps(result, indent=2))
        print("Structural prompt check only; no latency or actual KV cache reuse was measured.")
        return result["exit_code"]
    print("Forge prefix-test replay (no inference):")
    for row in result["results"]:
        print(
            f"  repeat {row['repeat']} / {row['condition']}: {row['status']} (expected {row['expected']}), {row['shared_chars']} shared chars; need {row['required_chars']}"
        )
    print(result["boundary"])
    return 0 if result["all_expected_outcomes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
