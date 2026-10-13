"""The validation driver decides which trials count, so its bookkeeping is tested."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gate_validate as gv


@pytest.fixture
def driver(tmp_path, monkeypatch):
    state = {"ac": True, "n": 0}

    def fake_trial(name, questions, policy):
        state["n"] += 1
        return {"verdict": "pass", "change_pct": 1.0, "ci_pct": [-5.0, 7.0], "seconds": 1.0}

    monkeypatch.setattr(gv, "one_trial", fake_trial)
    monkeypatch.setattr(gv, "power_state", lambda: {"on_ac": state["ac"]})
    monkeypatch.setattr(gv, "results_dir", lambda sub=None: tmp_path)
    monkeypatch.setattr(gv, "manifest", lambda **kw: {"m": 1})
    monkeypatch.setattr(gv, "vllm_image", lambda: None)
    monkeypatch.setattr(gv, "f1_questions", lambda: ["q"])
    return tmp_path, state


def _final(d):
    return json.loads((d / "v1_aa.json").read_text(encoding="utf-8"))


def test_a_killed_run_resumes_after_its_kept_trials_and_records_why(driver):
    d, state = driver
    gv.run("v1_aa", 2, smoke=False)
    assert [t["trial"] for t in _final(d)["trials"]] == [1, 2]
    with pytest.raises(SystemExit, match="resume-note"):
        gv.run("v1_aa", 4, smoke=False)  # an existing run is never silently extended
    gv.run("v1_aa", 4, smoke=False, resume_note="machine slept")
    f = _final(d)
    assert [t["trial"] for t in f["trials"]] == [1, 2, 3, 4] and state["n"] == 4
    assert f["resumed"][0]["after_trial"] == 2 and f["resumed"][0]["note"] == "machine slept"
    lines = (d / "v1_aa.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4


def test_power_loss_discards_that_trial_and_stops(driver, monkeypatch):
    d, _ = driver
    calls = {"n": 0}

    def power():
        calls["n"] += 1
        return {"on_ac": calls["n"] < 3}  # start ok, trial 1 ok, lost during trial 2

    monkeypatch.setattr(gv, "power_state", power)
    gv.run("v1_aa", 5, smoke=False)
    f = _final(d)
    assert [t["trial"] for t in f["trials"]] == [1]
    assert f["discarded"][0]["trial"] == 2 and "AC power lost" in f["stopped"]


def test_clopper_pearson_known_values():
    lo, hi = gv.clopper_pearson(0, 36)
    assert lo == 0.0 and hi == pytest.approx(1 - 0.025 ** (1 / 36), abs=1e-6)
    lo, hi = gv.clopper_pearson(5, 20)
    assert lo == pytest.approx(0.0866, abs=1e-3) and hi == pytest.approx(0.4910, abs=1e-3)


def test_affected_trials_stay_recorded_and_are_replaced(driver):
    d, state = driver
    gv.run("v1_aa", 4, smoke=False)
    gv.mark_affected("v1_aa", [2, 3], "a test run overlapped", "session log")
    gv.mark_affected("v1_aa", [2], "marked twice", "x")  # idempotent per trial
    with pytest.raises(SystemExit, match="no trial"):
        gv.mark_affected("v1_aa", [9], "r", "e")
    gv.run("v1_aa", 4, smoke=False, resume_note="replacements for affected trials")
    f = _final(d)
    assert [t["trial"] for t in f["trials"]] == [1, 2, 3, 4, 5, 6]  # 2 and 3 kept, 5-6 added
    assert [a["trial"] for a in f["affected"]] == [2, 3] and state["n"] == 6
    assert f["affected"][0]["reason"] == "a test run overlapped"
    gv.run("v1_aa", 4, smoke=False, resume_note="nothing left to do")
    assert len(_final(d)["trials"]) == 6 and state["n"] == 6  # already complete


def test_a_cut_off_jsonl_line_is_kept_aside_and_never_counted(driver):
    d, state = driver
    gv.run("v1_aa", 2, smoke=False)
    with (d / "v1_aa.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"verdict": "pass", "tri')  # the machine died mid-write
    gv.run("v1_aa", 3, smoke=False, resume_note="killed mid-write")
    f = _final(d)
    assert [t["trial"] for t in f["trials"]] == [1, 2, 3] and state["n"] == 3
    assert f["resumed"][0]["cut_lines"] == 1
    assert (d / "v1_aa.jsonl.cut").read_text(encoding="utf-8").startswith('{"verdict"')
    assert len((d / "v1_aa.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_summary_counts_affected_trials_only_in_their_own_row(driver):
    d, _ = driver
    gv.run("v1_aa", 3, smoke=False)
    gv.mark_affected("v1_aa", [1], "overlap", "log")
    gv.run("v1_aa", 3, smoke=False, resume_note="replace")
    gv.summarize()
    text = (d / "validation.md").read_text(encoding="utf-8")
    assert "| v1_aa | 3/3 |" in text and "| v1_aa incl. affected | 4 (all kept) |" in text
    assert "v1_aa trial 1 affected by competing work" in text


def test_cpu_sampler_reports_a_share_or_nothing():
    with gv.CpuSampler() as c:
        sum(i * i for i in range(200_000))
    r = c.result
    assert r is None or (0 <= r["busy_mean_pct"] <= 100 and 0 <= r["busy_max_1s_pct"] <= 100)
