"""scripts/live_github_run.py orchestration with the GitHub flows stubbed: it passes only
when Guard flags R1, repair is verified, and replays return the same PRs."""

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def live(monkeypatch):
    spec = importlib.util.spec_from_file_location("live_github_run", ROOT / "scripts/live_github_run.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_github_run"] = mod
    spec.loader.exec_module(mod)

    class App:
        async def app_info(self):
            return {"slug": "furnace-dev", "installations": [{"id": 1}]}

    monkeypatch.setattr(mod.cli, "_app", lambda: App())
    monkeypatch.setattr(mod.cli, "_suite", lambda p: [])
    monkeypatch.setattr(mod.cli, "_questions", lambda p: ["q"])
    monkeypatch.setattr(mod.cli, "_target", lambda no_endpoint: None)

    async def r1(app, repo, head, base):
        return {"number": 7, "url": "https://github.com/o/r/pull/7", "opened": True}

    monkeypatch.setattr(mod, "ensure_r1_pr", r1)
    return mod


def _stub(monkeypatch, mod, *, conclusion="failure", status="verified"):
    calls = {"forge": 0, "repair": 0}

    async def forge_pr(app, repo, **kw):
        calls["forge"] += 1
        return {"pr": {"number": 3, "url": "u3", "reused": calls["forge"] > 1}, "validation": {}}

    async def guard_pr(app, repo, number, **kw):
        assert kw["rerun"] is True and number == 7
        return {"check_id": 9, "conclusion": conclusion, "title": "t"}

    async def repair_pr(app, repo, number, **kw):
        calls["repair"] += 1
        pr = {"number": 11, "url": "u11", "reused": calls["repair"] > 1} if status == "verified" else None
        return {"status": status, "pr": pr, "perf": {"summary": "s", "reasons": ["r"]}}

    monkeypatch.setattr(mod.flows, "forge_pr", forge_pr)
    monkeypatch.setattr(mod.flows, "guard_pr", guard_pr)
    monkeypatch.setattr(mod.flows, "repair_pr", repair_pr)
    return calls


async def test_full_run_passes_only_with_same_prs_on_replay(live, monkeypatch):
    calls = _stub(monkeypatch, live)
    res = await live.main_async(argparse.Namespace(repo="o/r", head="r1-request-id", base="main"))
    assert res["verdict"] == "PASS", res["checks"]
    assert [s["step"] for s in res["steps"]] == [
        "check", "forge", "r1_pr", "guard", "repair", "replay_forge", "replay_repair",
    ]  # fmt: skip
    assert calls == {"forge": 2, "repair": 2}


async def test_guard_missing_r1_is_not_a_pass(live, monkeypatch):
    _stub(monkeypatch, live, conclusion="success", status="rejected")
    res = await live.main_async(argparse.Namespace(repo="o/r", head="r1-request-id", base="main"))
    assert res["verdict"].startswith("INCOMPLETE") and not res["checks"]["guard_flagged_r1"]


async def test_a_failing_step_stops_the_run_and_is_recorded(live, monkeypatch):
    _stub(monkeypatch, live)

    async def broken(app, repo, **kw):
        return {"pr": None, "reason": "validation failed; no pull request opened"}

    monkeypatch.setattr(live.flows, "forge_pr", broken)
    res = await live.main_async(argparse.Namespace(repo="o/r", head="r1-request-id", base="main"))
    assert [s["step"] for s in res["steps"]] == ["check", "forge"]
    assert "validation failed" in res["steps"][1]["error"]
    assert res["verdict"].startswith("INCOMPLETE")
