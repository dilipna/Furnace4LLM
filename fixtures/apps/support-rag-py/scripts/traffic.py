"""Simulated user traffic against a running Kilnworks Assist (POST /chat).

Produces the app's own production-style trace log (traces/llm_calls.jsonl) that
Furnace fingerprints and evaluates. Questions: every documented fact, plus
out-of-scope questions (should get the documented not-found answer) and
requests that need a human (should end with an ESCALATE line).

    python scripts/traffic.py --url http://localhost:8080 --rate 2 --repeat 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent

OUT_OF_SCOPE = [
    "Can I use Kilnworks to control a pizza oven?",
    "What is the best glaze recipe for celadon?",
    "Do you integrate with Microsoft Teams?",
    "Which cone should I fire porcelain to?",
    "Is there an Android tablet app for kiln wiring diagrams?",
    "What is the price of the Enterprise plan?",
]
NEEDS_HUMAN = [
    "I was charged twice this month and want a refund.",
    "My kiln smells like burning plastic during firing, what should I do?",
    "Please delete my account and all my data.",
    "The lid sensor keeps stopping my firing, can you turn it off for me?",
]


def questions() -> list[dict]:
    facts = json.loads((ROOT / "docs" / "facts.json").read_text(encoding="utf-8"))
    qs = [{"question": f["question"], "kind": "fact", "doc_id": f["doc_id"]} for f in facts]
    qs += [{"question": q, "kind": "out_of_scope"} for q in OUT_OF_SCOPE]
    qs += [{"question": q, "kind": "needs_human"} for q in NEEDS_HUMAN]
    return qs


async def ask(client: httpx.AsyncClient, url: str, q: dict) -> dict:
    t0 = time.perf_counter()
    async with client.stream("POST", f"{url}/chat", json={"question": q["question"]}) as r:
        text = "".join([chunk async for chunk in r.aiter_text()])
    return {**q, "answer": text, "status": r.status_code, "client_latency_ms": (time.perf_counter() - t0) * 1000}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--rate", type=float, default=2.0, help="mean arrivals per second (Poisson)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "traces" / "client_answers.jsonl"))
    a = ap.parse_args()
    rng = random.Random(a.seed)
    qs = questions() * a.repeat
    rng.shuffle(qs)
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=120) as client:
        tasks = []
        for q in qs:
            tasks.append(asyncio.create_task(ask(client, a.url, q)))
            await asyncio.sleep(rng.expovariate(a.rate))
        results = await asyncio.gather(*tasks)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    ok = sum(r["status"] == 200 for r in results)
    print(f"{ok}/{len(results)} requests succeeded; answers in {a.out}")


if __name__ == "__main__":
    asyncio.run(main())
