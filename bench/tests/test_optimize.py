"""The optimizer's quality score is a deterministic rule; test what it accepts and refuses."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import optimize

REF = "The Studio plan costs $29 per month and supports up to 3 kilns."


@pytest.mark.parametrize(
    ("answer", "ok"),
    [
        ("It is $29 per month for up to 3 kilns [doc:plans].", True),
        ("$29/month, 3 kilns", True),
        ("It is $129 per month for 13 kilns.", False),  # digits inside other numbers do not count
        ("It is $29.50 per month for 3 kilns.", False),  # 29.50 is not 29
        ("It is $29 per month.", False),  # every documented number is required
        ("", False),
    ],
)
def test_facts_pass_needs_every_documented_number_as_a_whole_number(answer, ok):
    assert optimize.facts_pass(REF, answer) is ok


def test_answers_without_numbers_are_not_scored():
    assert optimize.facts_pass("Kilnworks accepts Visa, Mastercard and SEPA.", "Visa") is None


def test_grid_and_baseline():
    names = [g["name"] for g in optimize.GRID]
    assert len(names) == 8 and len(set(names)) == 8 and optimize.BASELINE in names


def test_sentence_final_number_counts():
    assert optimize.facts_pass("Support replies within 4 business hours.", "Within 4.") is True


def test_measure_perf_runs_the_requested_number_of_runs(monkeypatch):
    seen = []

    class _Lv:
        slo_goodput_rps, failure_rate, telemetry = 6.0, 0.0, {}

        class ttft_ms:
            p95 = 100.0

    class _Res:
        class report:
            levels = [_Lv()]

    async def fake(target, spec, plan):
        seen.append(plan.seed)
        return _Res()

    monkeypatch.setattr(optimize, "run_benchmark", fake)
    cfg = optimize.GRID[0]
    assert len(optimize.measure_perf(cfg)) == optimize.PERF_RUNS
    seen.clear()
    assert len(optimize.measure_perf(cfg, n_runs=1, seed0=5003)) == 1 and seen == [5003]
