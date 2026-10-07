"""RQ2 judge stage with a mock LLM: split protocol, few-shot provenance and TPR/TNR."""

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rq2
from furnace.llm.client import LLMClient


def _setup(tmp_path, monkeypatch, n=40):
    queue, labels = [], []
    for i in range(n):
        bad = i % 3 == 0  # every third answer is ungrounded
        queue.append(
            {
                "id": f"f1-{i:03d}",
                "question": f"q{i}?",
                "context": f"[doc:a] fact {i}",
                "answer": f"{'invented' if bad else 'supported'} answer {i}",
                "retrieved_ids": ["a"],
            }
        )
        labels.append({"id": f"f1-{i:03d}", "grounded": not bad, "correct": None, "notes": ""})
    (tmp_path / "q.jsonl").write_text("".join(json.dumps(q) + "\n" for q in queue))
    (tmp_path / "l.jsonl").write_text("".join(json.dumps(x) + "\n" for x in labels))
    monkeypatch.setattr(rq2, "QUEUE", tmp_path / "q.jsonl")
    monkeypatch.setattr(rq2, "LABELS", tmp_path / "l.jsonl")


def _client(seen: list[list[dict]]) -> LLMClient:
    def handler(req: httpx.Request) -> httpx.Response:
        msgs = json.loads(req.content)["messages"]
        seen.append(msgs)
        verdict = "FAIL" if "invented" in msgs[-1]["content"] else "PASS"
        content = json.dumps({"verdict": verdict, "critique": "mock"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    return LLMClient(
        model="mock-judge",
        base_url="http://mock/v1",
        cache_dir=None,
        requests_per_minute=10_000,
        transport=httpx.MockTransport(handler),
    )


async def test_judge_part_reports_dev_and_test_with_train_only_few_shot(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    seen: list[list[dict]] = []
    out = await rq2.judge_part(_client(seen))
    assert out["status"] == "run" and out["errors"] == 0 and out["few_shot"] == 4
    # 40 items: 8 train (few-shot pool), 16 dev, 16 test; train items are never judged
    assert out["dev"]["n"] + out["test"]["n"] == 32 == len(seen)
    for part in ("dev", "test"):
        assert out[part]["tpr"] == 1.0 and out[part]["tnr"] == 1.0  # the mock judge is perfect
    assert out["test"]["trusted"] is False  # n < 20 on the test split: not trusted yet
    shots_in_prompt = [m["content"] for m in seen[0][1:-1] if m["role"] == "user"]
    judged_answers = {msgs[-1]["content"] for msgs in seen}
    assert len(shots_in_prompt) == 4 and not set(shots_in_prompt) & judged_answers
    assert out["usage"]["calls"] == 32


async def test_judge_part_without_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(rq2, "LABELS", tmp_path / "missing.jsonl")
    out = await rq2.judge_part(_client([]))
    assert out == {"status": "not_run", "reason": "no human labels yet"}
