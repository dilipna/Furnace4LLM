"""Acceptance/write boundaries: real repair loop and edits; sandbox/GitHub/inference mocked."""

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest
from furnace_bench.schema import BenchTarget

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "fixtures/scenarios"))
from f1_scenarios import by_name, materialize
from f1_suite import F1_SUITE
from furnace.github import flows
from furnace.github.client import GitHubApp
from furnace.guardian.impact import analyze_impact, analyze_tree
from furnace.guardian.perf_gate import (
    METHOD_WELCH,
    GatePolicy,
    accept_repair,
    verified_repair_performance,
)
from furnace.guardian.repair import loop
from furnace.sandbox.docker_sandbox import SandboxResult


def evidence():
    def cmp(base, value, change, ci, verdict):
        return {
            "metric": "ttft_gmean_ms",
            "method": METHOD_WELCH.format(pct=90),
            "confidence": 0.90,
            "runs": 3,
            "baseline_runs": [base] * 3,
            "value_runs": [value] * 3,
            "baseline": base,
            "value": value,
            "change_pct": change,
            "ci_pct": ci,
            "verdict": verdict,
        }

    return {
        "head_vs_base": cmp(100, 1000, 900, [700, 1100], "block"),
        "candidate_vs_base": cmp(100, 102, 2, [-5, 8], "pass"),
        "candidate_vs_head": cmp(1000, 102, -89.8, [-92, -87], "pass"),
        "within_budget": True,
        "summary": "synthetic interval evidence, not inference",
    }


def bad_evidence(kind):
    p = evidence()
    if kind == "missing":
        return {}
    if kind == "skipped_full":
        return p | {"status": "skipped"}
    if kind == "error_full":
        return p | {"error": "measurement did not run"}
    if kind == "blocked_head":
        p["candidate_vs_head"]["verdict"] = "block"
    if kind == "blocked_base":
        p["candidate_vs_base"]["verdict"] = "block"
    if kind == "skipped":
        return {"within_budget": True, "status": "skipped"}
    if kind == "failed":
        p["within_budget"] = False
    elif kind == "inconclusive":
        p["candidate_vs_head"].update(change_pct=-1, ci_pct=[-9, 6], verdict="inconclusive")
    elif kind == "measurement_error":
        p["head_vs_base"] = {"verdict": "error", "reason": "endpoint unavailable"}
    elif kind == "nan":
        p["candidate_vs_base"]["ci_pct"][0] = float("nan")
    elif kind == "infinity":
        p["candidate_vs_head"]["value"] = float("inf")
    elif kind == "malformed":
        p["candidate_vs_head"]["ci_pct"] = "not an interval"
    elif kind == "truthy":
        p["within_budget"] = "false"
    elif kind == "summary_only":
        p["candidate_vs_base"]["ci_pct"] = None
        p["candidate_vs_head"]["ci_pct"] = None
    elif kind == "short_runs":
        p["candidate_vs_head"]["runs"] = 1
    return p


BAD = [
    "blocked_head",
    "blocked_base",
    "skipped_full",
    "error_full",
    "missing",
    "skipped",
    "failed",
    "inconclusive",
    "measurement_error",
    "nan",
    "infinity",
    "malformed",
    "truthy",
    "summary_only",
    "short_runs",
    "exception",
]


@pytest.fixture
def repair_env(tmp_path, monkeypatch):
    base = materialize(None, tmp_path / "base-source")
    head = materialize(by_name("r1_dynamic_head"), tmp_path / "head-source")
    impact = analyze_impact(analyze_tree(base), analyze_tree(head), F1_SUITE)
    calls = []

    def render(root, questions):
        # Only the render/sandbox boundary is mocked, not the repair strategies or acceptance.
        return "base" if root.name == "base" else "head"

    monkeypatch.setattr(loop, "render_in_sandbox", render)
    monkeypatch.setattr(loop, "min_shared_prefix", lambda data: 100 if data == "base" else 10)

    def sandbox(root, *targets):
        calls.append((root.name, targets))
        return SandboxResult(1 if root.name == "head" else 0, "synthetic tests", "", 0.01, False)

    monkeypatch.setattr(loop, "pytest_in_sandbox", sandbox)
    return base, head, impact, calls


def run_loop(env, callback=None):
    base, head, impact, _ = env
    return loop.repair_prefix_instability(
        base, head, impact, questions=["q1", "q2"], change_label="test", perf_check=callback
    )


def test_no_callback_is_functional_only(repair_env):
    out = run_loop(repair_env)
    assert out.attempt.status.value == "functional_only"
    assert out.files and out.patch and out.attempt.selected is not None
    assert out.perf == {}
    assert len(repair_env[3]) == 4  # head/base reproduction, candidate regression/existing


@pytest.mark.parametrize("kind", BAD)
def test_required_bad_evidence_cannot_accept_candidate(repair_env, kind):
    measured = []

    def callback(*args):
        measured.append(args[2].name)
        if kind == "exception":
            raise ValueError("measurement unavailable")
        return bad_evidence(kind)

    out = run_loop(repair_env, callback)
    assert out.attempt.status.value == "rejected"
    assert out.functional_passed  # functional success does not imply performance verification
    assert not out.files and not out.patch and out.attempt.selected is None
    assert len(measured) == 2 and len(repair_env[3]) == 6  # both strategies actually attempted


def test_complete_passing_evidence_retains_acceptance(repair_env):
    out = run_loop(repair_env, lambda *a: evidence())
    assert out.attempt.status.value == "verified" and out.files
    assert out.attempt.selected == 0 and len(repair_env[3]) == 4


@pytest.fixture
def flow_env(repair_env, monkeypatch):
    writes, scopes = [], []
    base, head, _, _ = repair_env

    class Repo:
        full_name = "o/r"
        token = "mock"

        async def pull(self, number):
            return {
                "number": number,
                "base_sha": "b" * 40,
                "head_sha": "h" * 40,
                "head_repo": "o/r",
                "head_ref": "regression",
            }

        async def open_draft_pr(self, **kwargs):
            writes.append(kwargs)
            return {"url": "https://example.invalid/draft", "number": 9}

    async def token(app, repo, permissions, expected_installation=None):
        scopes.append(permissions)
        return Repo()

    async def fetch(repo, sha, token, dest):
        shutil.copytree(base if sha.startswith("b") else head, dest)
        return dest

    monkeypatch.setattr(flows, "_token", token)
    monkeypatch.setattr(flows, "fetch_revision", fetch)
    # Actual flow callback runs the mocked measurement boundary, then validates its result.
    monkeypatch.setattr(flows, "run_gate", lambda *a, **k: {})
    return writes, scopes


async def call_flow(target):
    return await flows.repair_pr(
        GitHubApp("1", "unused"),
        "o/r",
        5,
        suite=F1_SUITE,
        target=target,
        questions=["q1", "q2"],
        open_pr=True,
    )


@pytest.mark.parametrize("kind", BAD)
async def test_required_bad_evidence_never_opens_draft(flow_env, monkeypatch, kind):
    def measured(*a):
        if kind == "exception":
            raise ValueError("measurement unavailable")
        return bad_evidence(kind)

    monkeypatch.setattr(flows, "repair_perf_check", measured)
    out = await call_flow(BenchTarget(base_url="http://localhost:8100/v1", model="lab"))
    assert out["status"] == "rejected" and out["pr"] is None
    assert out["verification"] == {"functional": "passed", "performance": "not_verified"}
    assert flow_env[0] == [] and len(flow_env[1]) == 1  # no write token minted


async def test_measured_verified_draft_is_created(flow_env, monkeypatch):
    monkeypatch.setattr(flows, "repair_perf_check", lambda *a: evidence())
    out = await call_flow(BenchTarget(base_url="http://localhost:8100/v1", model="lab"))
    assert out["status"] == "verified" and out["pr"] is not None
    assert out["verification"] == {"functional": "passed", "performance": "passed"}
    assert len(flow_env[0]) == 1 and len(flow_env[1]) == 2
    assert flow_env[0][0]["new_branch"].startswith("furnace/repair-v2-")
    assert "performance verified" in flow_env[0][0]["body"].lower()


async def test_offline_draft_is_explicitly_unverified(flow_env):
    out = await call_flow(None)
    assert out["status"] == "functional_only" and out["pr"] is not None
    assert out["verification"] == {"functional": "passed", "performance": "unverified"}
    assert len(flow_env[0]) == 1
    pr = flow_env[0][0]
    assert "UNVERIFIED" in pr["title"] and "performance unverified" in pr["body"].lower()
    assert "not measured" in pr["body"].lower()
    assert pr["new_branch"].startswith("furnace/proposal-v2-")


def test_cli_offline_output_is_explicit(flow_env, monkeypatch, capsys):
    from furnace import cli

    monkeypatch.setattr(cli, "_app", object)
    monkeypatch.setattr(cli, "_suite", lambda p: F1_SUITE)
    assert (
        cli.main(["gh-repair", "o/r", "5", "--suite", "unused", "--no-endpoint", "--open-pr"]) == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "functional_only"
    assert out["verification"]["performance"] == "unverified"
    assert len(flow_env[0]) == 1 and "UNVERIFIED" in flow_env[0][0]["title"]


@pytest.mark.parametrize("bad", [None, [], [float("nan"), -1], [-1, float("inf")], "bad"])
def test_accept_repair_refuses_invalid_intervals(bad):
    p = evidence()
    p["candidate_vs_head"]["ci_pct"] = copy.deepcopy(bad)
    ok, _ = accept_repair(
        p["head_vs_base"], p["candidate_vs_base"], p["candidate_vs_head"], GatePolicy()
    )
    assert not ok


def test_historical_measured_acceptance_is_preserved():
    root = Path(__file__).resolve().parents[3]
    attempts = json.loads((root / "bench/results/2026-10-12-gate-validation/rq5.json").read_text())[
        "attempts"
    ]
    measured = [a for a in attempts if a["status"] == "verified"]
    assert len(measured) == 3
    assert all(verified_repair_performance(a["perf"], GatePolicy()) for a in measured)


def test_tolerance_inconclusive_can_still_meet_the_existing_repair_bounds(repair_env):
    p = evidence()
    p["candidate_vs_base"].update(change_pct=3, ci_pct=[-6, 12], verdict="inconclusive")
    out = run_loop(repair_env, lambda *a: p)
    assert out.attempt.status.value == "verified" and out.files


def test_rounding_at_noise_tolerance_does_not_change_repair_acceptance():
    p = evidence()
    # The unrounded upper bound could be 10.04%, while the stored bound is 10.0%.
    # INCONCLUSIVE vs +10% still satisfies the separate repair bound of <25%.
    p["candidate_vs_base"].update(change_pct=3, ci_pct=[-6, 10.0], verdict="inconclusive")
    assert verified_repair_performance(p, GatePolicy())


@pytest.mark.parametrize("kind", ["verdict", "samples", "metadata"])
def test_malformed_nested_evidence_is_not_verified(kind):
    p = evidence()
    if kind == "verdict":
        p["head_vs_base"]["verdict"] = []
    elif kind == "samples":
        p["head_vs_base"]["samples_ms"] = {"baseline": [[float("inf")]]}
    else:
        p["candidate_vs_base"]["confidence"] = "0.90"
    assert not verified_repair_performance(p, GatePolicy())


async def test_write_boundary_refuses_a_forged_verified_label(flow_env, repair_env, monkeypatch):
    outcome = run_loop(repair_env)  # real functional-only candidate and files
    outcome.attempt.status = loop.RepairStatus.verified
    monkeypatch.setattr(flows, "repair_prefix_instability", lambda *a, **k: outcome)
    out = await call_flow(BenchTarget(base_url="http://localhost:8100/v1", model="lab"))
    assert out["status"] == "rejected" and out["pr"] is None and flow_env[0] == []


async def test_unsupported_regression_opens_nothing(flow_env, monkeypatch):
    monkeypatch.setattr(loop, "prefix_instability_node", lambda impact: None)
    out = await call_flow(None)
    assert out["status"] == "rejected" and out["pr"] is None and flow_env[0] == []


def test_functional_failure_never_reaches_measurement(repair_env, monkeypatch):
    def sandbox(root, *targets):
        return SandboxResult(0 if root.name == "base" else 1, "failed test", "", 0.01, False)

    monkeypatch.setattr(loop, "pytest_in_sandbox", sandbox)
    out = run_loop(repair_env, lambda *a: pytest.fail("performance must not run"))
    assert out.attempt.status.value == "rejected" and not out.files and not out.functional_passed
