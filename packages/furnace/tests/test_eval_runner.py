from furnace.contracts.evals import Verdict
from furnace.evals.runner import EvaluatorSpec, case_from_log, run_suite


def log(answer: str, ttft: float = 80.0) -> dict:
    ctx = "[doc:pairing] How do I pair?\nHold PAIR.\n\n[doc:plans] Price\n$29"
    return {
        "route": "/chat",
        "model": "lab",
        "messages": [
            {"role": "system", "content": "You are Kilnworks Assist."},
            {
                "role": "user",
                "content": f"CONTEXT:\n{ctx}\n\nQUESTION: How do I pair a controller?",
            },
        ],
        "completion": answer,
        "prompt_tokens": 1500,
        "completion_tokens": 30,
        "latency_ms": 900.0,
        "ttft_ms": ttft,
    }


def test_case_from_app_log_recovers_question_and_retrieved_ids():
    c = case_from_log(log("Hold PAIR [doc:pairing]."))
    assert c.input == "How do I pair a controller?"
    assert c.retrieved_ids == ["pairing", "plans"]
    assert c.prompt_tokens == 1500 and c.ttft_ms == 80.0
    assert c.rendered_prompt and c.rendered_prompt.startswith("system\nYou are Kilnworks Assist.")


def test_run_suite_summarizes_per_evaluator():
    cases = [
        case_from_log(log("Hold PAIR [doc:pairing].")),
        case_from_log(log("Hold PAIR.", ttft=400)),
    ]
    evs = [
        EvaluatorSpec("ev:citation_required", "citation_required"),
        EvaluatorSpec("ev:ttft", "latency_threshold", {"max_ttft_ms": 300}),
    ]
    res = run_suite(cases, evs)
    assert res.summary() == {
        "ev:citation_required": {"PASS": 1, "FAIL": 1},
        "ev:ttft": {"PASS": 1, "FAIL": 1},
    }
    (fail,) = res.failures("ev:citation_required")
    assert fail.case_index == 1 and fail.verdict == Verdict.FAIL
