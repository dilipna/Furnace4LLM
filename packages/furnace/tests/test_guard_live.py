"""Live Guard events on a real F1 scenario: impact first, then each selected check in order,
then the verdict. Executors are stubbed (no Docker or endpoint); impact analysis is real."""

from furnace.guardian import execute, live
from furnace.guardian.execute import ItemResult


def test_local_guard_event_sequence(monkeypatch):
    ran: list[str] = []

    def fake(item, ctx):
        ran.append(item.key)
        verdict = "fail" if item.key == "check:prompt_prefix_stable" else "pass"
        return ItemResult(item.key, verdict, "stub")

    monkeypatch.setattr(execute, "EXECUTORS", dict.fromkeys(execute.EXECUTORS, fake))
    monkeypatch.setattr(execute, "CHECKS", dict.fromkeys(execute.CHECKS, fake))
    monkeypatch.setattr(live, "prepare", lambda b, h: (b.parent / "work", b, h))
    events: list[dict] = []
    out = live.run_local_guard("r1_dynamic_head", events.append, with_endpoint=False)

    types = [e["type"] for e in events]
    assert types[:2] == ["phase", "impact"] and types[-1] == "verdict"
    impact = events[1]
    touched = {t["key"] for t in impact["touched"]}
    assert any(k.startswith("prompt:") for k in touched)
    assert {"check:prompt_prefix_stable", "bench:chat_perf_gate"} <= {
        s["key"] for s in impact["selected"]
    }
    # every node the UI draws exists, and every edge connects drawn nodes
    keys = {n["key"] for n in impact["nodes"]}
    assert touched <= keys
    assert all(e["src"] in keys and e["dst"] in keys for e in impact["edges"])
    # checks: start then done, one pair per selected item, in suite order
    checks = [e for e in events if e["type"].startswith("check_")]
    assert [e["type"] for e in checks] == ["check_start", "check_done"] * len(ran)
    assert [e["key"] for e in checks[::2]] == ran == [s["key"] for s in impact["selected"]]
    assert out["conclusion"] == "failure" and out["executed"] == len(ran)


def test_unknown_scenario_is_refused():
    import pytest

    with pytest.raises(ValueError, match="unknown scenario"):
        live.run_local_guard("nope", lambda e: None, with_endpoint=False)
