"""scripts/live_github_verify.py: the pure checks decide what 'verified on GitHub' means,
so each must reject the wrong state, not only accept the right one."""

import hashlib
import hmac
import importlib.util
import sys
from pathlib import Path

import pytest
from furnace.github.client import verify_webhook

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def v():
    spec = importlib.util.spec_from_file_location(
        "live_github_verify", ROOT / "scripts/live_github_verify.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_github_verify"] = mod
    spec.loader.exec_module(mod)
    return mod


GOOD_APP = {
    "permissions": {"contents": "write", "pull_requests": "write", "checks": "write", "metadata": "read"},
    "events": ["pull_request"],
}  # fmt: skip
GOOD_INST = {"repository_selection": "selected", "repositories": ["o/furnace-demo-f1"]}


def test_exact_manifest_grant_passes(v):
    assert v.check_permissions(GOOD_APP, GOOD_INST, "o/furnace-demo-f1") == []


@pytest.mark.parametrize(
    ("app", "inst", "needle"),
    [
        ({**GOOD_APP, "permissions": {**GOOD_APP["permissions"], "administration": "write"}}, GOOD_INST, "extra"),
        ({**GOOD_APP, "permissions": {**GOOD_APP["permissions"], "checks": "read"}}, GOOD_INST, "missing"),
        ({**GOOD_APP, "events": ["pull_request", "push"]}, GOOD_INST, "events"),
        (GOOD_APP, {**GOOD_INST, "repository_selection": "all"}, "'all'"),
        (GOOD_APP, {**GOOD_INST, "repositories": ["o/other"]}, "not among"),
    ],
)  # fmt: skip
def test_any_broader_or_different_grant_is_reported(v, app, inst, needle):
    problems = v.check_permissions(app, inst, "o/furnace-demo-f1")
    assert problems and any(needle in p for p in problems)


def _pr(**kw):
    pr = {
        "number": 5,
        "draft": True,
        "head": {"ref": "furnace/repair-abc"},
        "base": {"ref": "r1-request-id"},
        "user": {"login": "furnace-dev[bot]", "type": "Bot"},
        "_first_parent": "a" * 40,
    }
    pr.update(kw)
    return pr


def test_draft_pr_checks(v):
    assert v.check_draft_pr(_pr(), base_ref="r1-request-id", built_on="a" * 40) == []
    assert (
        "not a draft"
        in v.check_draft_pr(_pr(draft=False), base_ref="r1-request-id", built_on=None)[0]
    )
    assert (
        "not under furnace/"
        in v.check_draft_pr(_pr(head={"ref": "main"}), base_ref="r1-request-id", built_on=None)[0]
    )
    assert (
        "targets"
        in v.check_draft_pr(_pr(base={"ref": "main"}), base_ref="r1-request-id", built_on=None)[0]
    )
    assert (
        "opened by"
        in v.check_draft_pr(
            _pr(user={"login": "me", "type": "User"}), base_ref="r1-request-id", built_on=None
        )[0]
    )
    assert "built on" in v.check_draft_pr(_pr(), base_ref="r1-request-id", built_on="b" * 40)[0]  # fmt: skip


def test_check_run_attribution(v):
    run = {"head_sha": "h" * 40, "app": {"id": 42}, "status": "completed"}
    assert v.check_run_problems(run, head_sha="h" * 40, app_id="42") == []
    assert v.check_run_problems({**run, "head_sha": "x" * 40}, head_sha="h" * 40, app_id="42")
    assert v.check_run_problems({**run, "app": {"id": 7}}, head_sha="h" * 40, app_id="42")
    assert v.check_run_problems({**run, "status": "in_progress"}, head_sha="h" * 40, app_id="42")


def test_probe_signatures_match_what_the_receiver_verifies(v):
    body = b'{"zen":"x"}'
    sig = v.sign("s3cret", body)
    assert sig == "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_webhook("s3cret", body, sig)
    assert not verify_webhook("s3cret", body + b" ", sig)
    assert not verify_webhook("s3cret", body, v.sign("other", body))


def test_delivery_times_compare_across_z_and_offset_forms(v):
    assert v._utc("2026-10-12T19:30:01Z") > v._utc("2026-10-12T19:30:00+00:00")
    assert v._utc("2026-10-12T15:30:00-04:00") == v._utc("2026-10-12T19:30:00Z")
    assert v._utc(None) < v._utc("2000-01-01T00:00:00Z")
