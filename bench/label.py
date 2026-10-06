"""Label the RQ2 queue in the terminal: is each real F1 answer grounded and correct?

  uv run python bench/label.py           # resumes where you stopped; q to quit

Writes one JSON line per item to bench/labels/f1_labels.jsonl:
  {"id", "grounded": bool, "correct": bool | null, "notes", "labeler", "ts"}
grounded = every factual claim is supported by the CONTEXT shown (or it is a proper refusal).
correct  = the answer actually answers the question as the documentation would (null = n/a).
"""

from __future__ import annotations

import datetime as dt
import getpass
import json
import textwrap

from rq2 import LABELS, QUEUE


def ask(prompt: str, allowed: dict[str, object]) -> object:
    while True:
        a = input(prompt).strip().lower()
        if a in allowed:
            return allowed[a]
        print(f"  answer one of: {', '.join(allowed)}")


def main() -> None:
    queue = [
        json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    done = set()
    if LABELS.exists():
        done = {
            json.loads(line)["id"]
            for line in LABELS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    todo = [q for q in queue if q["id"] not in done]
    print(f"{len(done)} labeled, {len(todo)} to go.\n")
    yn = {"y": True, "n": False, "q": "quit"}
    for i, q in enumerate(todo, 1):
        print("=" * 100)
        print(f"[{i}/{len(todo)}] {q['id']}  model={q['model']}  kind={q['kind']}")
        print(f"QUESTION: {q['question']}\n")
        print("CONTEXT:\n" + textwrap.indent(q["context"][:2500], "  "))
        if q.get("gold_answer"):
            print(f"\nDOCUMENTED ANSWER: {q['gold_answer']}")
        print(f"\nMODEL ANSWER:\n  {q['answer']}\n")
        g = ask("grounded in the context? [y/n/q] ", yn)
        if g == "quit":
            break
        c = ask("correct answer to the question? [y/n/-(n/a)/q] ", {**yn, "-": None})
        if c == "quit":
            break
        notes = input("notes (optional): ").strip()
        rec = {
            "id": q["id"],
            "grounded": g,
            "correct": c,
            "notes": notes,
            "labeler": getpass.getuser(),
            "ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        }
        with LABELS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    print("\nsaved to", LABELS)


if __name__ == "__main__":
    main()
