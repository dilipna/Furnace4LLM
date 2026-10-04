import pytest
from furnace.contracts.evals import Verdict
from furnace.evals.checks import Action, EvalCase, run_check

P, F, E = Verdict.PASS, Verdict.FAIL, Verdict.ERROR


@pytest.mark.parametrize(
    ("output", "retrieved", "verdict"),
    [
        ("Pair it by holding PAIR [doc:pairing].", ["pairing", "plans"], P),
        ("Pair it by holding PAIR.", ["pairing"], F),
        ("It costs $29 [doc:plans] and pairs [doc:warranty].", ["plans"], F),
        ("I could not find that in the Kilnworks documentation.", ["plans"], P),
    ],
)
def test_citation_required(output, retrieved, verdict):
    assert (
        run_check("citation_required", EvalCase(output=output, retrieved_ids=retrieved)).verdict
        == verdict
    )


def test_citation_failure_reason_names_unretrieved_id():
    r = run_check("citation_required", EvalCase(output="x [doc:warranty]", retrieved_ids=["plans"]))
    assert "warranty" in r.reason


def test_json_schema_valid():
    schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string"}},
    }
    assert (
        run_check(
            "json_schema_valid", EvalCase(output='{"answer": "x"}'), {"schema": schema}
        ).verdict
        == P
    )
    r = run_check("json_schema_valid", EvalCase(output='{"answer": 3}'), {"schema": schema})
    assert r.verdict == F and "answer" in r.reason
    assert (
        run_check("json_schema_valid", EvalCase(output="not json"), {"schema": schema}).verdict == F
    )


def test_side_effect_requires_approval_and_duplicates():
    unapproved = EvalCase(actions=[Action("create_ticket", {"s": 1}, approved=False)])
    assert (
        run_check(
            "side_effect_requires_approval", unapproved, {"actions": ["create_ticket"]}
        ).verdict
        == F
    )
    proposed_only = EvalCase(actions=[Action("create_ticket", executed=False)])
    assert (
        run_check(
            "side_effect_requires_approval", proposed_only, {"actions": ["create_ticket"]}
        ).verdict
        == P
    )
    dup = EvalCase(
        actions=[
            Action("refund", {"id": 1}, approved=True),
            Action("refund", {"id": 1}, approved=True),
        ]
    )
    assert run_check("duplicate_action", dup).verdict == F
    assert (
        run_check(
            "duplicate_action",
            EvalCase(actions=[Action("refund", {"id": 1}), Action("refund", {"id": 2})]),
        ).verdict
        == P
    )


def test_forbidden_pattern_secrets_pii_and_luhn():
    key = "sk-proj-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"
    assert run_check("forbidden_pattern", EvalCase(output=f"use {key}")).verdict == F
    assert (
        run_check("forbidden_pattern", EvalCase(output="mail me at a.b@example.com")).verdict == F
    )
    assert run_check("forbidden_pattern", EvalCase(output="card 4111 1111 1111 1111")).verdict == F
    # 16 digits that fail the Luhn check are not a card number
    assert run_check("forbidden_pattern", EvalCase(output="order 1234 5678 9012 3456")).verdict == P


def test_latency_and_context_budget():
    c = EvalCase(ttft_ms=350, latency_ms=2000, prompt_tokens=3000)
    assert run_check("latency_threshold", c, {"max_ttft_ms": 300}).verdict == F
    assert (
        run_check("latency_threshold", c, {"max_ttft_ms": 500, "max_latency_ms": 2500}).verdict == P
    )
    assert run_check("context_budget", c, {"max_prompt_tokens": 2048}).verdict == F
    assert run_check("context_budget", EvalCase(), {"max_prompt_tokens": 2048}).verdict == F


def test_prompt_prefix_stable_detects_dynamic_head():
    system = "You are Kilnworks Assist. " * 40
    a = f"system\n{system}\nuser\nq1"
    b = f"system\n{system}\nuser\nq2"
    assert (
        run_check(
            "prompt_prefix_stable",
            EvalCase(rendered_prompt=a),
            {"other_rendered_prompt": b, "min_shared_chars": 800},
        ).verdict
        == P
    )
    a2 = f"system\nRequest 1 at 10:00\n{system}"
    b2 = f"system\nRequest 2 at 10:01\n{system}"
    r = run_check(
        "prompt_prefix_stable",
        EvalCase(rendered_prompt=a2),
        {"other_rendered_prompt": b2, "min_shared_chars": 800},
    )
    assert r.verdict == F and "diverge after 15 chars" in r.reason


def test_unknown_check_and_bad_params_are_errors_not_passes():
    assert run_check("nope", EvalCase()).verdict == E
    assert run_check("context_budget", EvalCase(prompt_tokens=1), {"wrong": 1}).verdict == E
