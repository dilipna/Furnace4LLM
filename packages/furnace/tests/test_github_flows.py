"""GitHub flows against a mock GitHub: call sequence, token scopes, fork refusal, and that a
crash still completes the check run (never left spinning). Sandbox work is stubbed."""

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from furnace.github import flows
from furnace.github.client import GUARD_PERMISSIONS, GitHubApp, GitHubError
from furnace.guardian.execute import ItemResult
from furnace.guardian.impact import SuiteItem

KEY = (
    rsa.generate_private_key(public_exponent=65537, key_size=2048)
    .private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    .decode()
)


class FakeGitHub:
    def __init__(self, head_repo="o/r", check_runs=None):
        self.calls: list[tuple[str, str, dict]] = []
        self.head_repo = head_repo
        self.base_sha = "b" * 40
        self.fail_interrupted_update = False
        self.check_runs = check_runs or []  # existing "Furnace Guard" runs on the head

    def __call__(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else {}
        self.calls.append((req.method, req.url.path, body))
        p = req.url.path
        if p == "/repos/o/r/installation":
            return httpx.Response(200, json={"id": 77})
        if p == f"/repos/o/r/commits/{'h' * 40}/check-runs" and req.method == "GET":
            assert req.url.params["check_name"] == "Furnace Guard"
            assert req.url.params["app_id"] == "123"  # only this App's check runs
            return httpx.Response(200, json={"check_runs": self.check_runs})
        if p == "/app/installations/77/access_tokens":
            return httpx.Response(201, json={"token": "t-scoped"})
        if p in ("/repos/o/r/pulls/5", "/repos/o/r/pulls/6"):
            return httpx.Response(
                200,
                json={
                    "number": 5,
                    "title": "add request id",
                    "base": {"ref": "main", "sha": self.base_sha},
                    "head": {"ref": "feat", "sha": "h" * 40, "repo": {"full_name": self.head_repo}},
                },
            )
        if p == "/repos/o/r/check-runs" and req.method == "POST":
            check_id = 990 + sum(m == "POST" and path == p for m, path, _ in self.calls)
            self.check_runs.insert(0, {"id": check_id, **body})
            return httpx.Response(201, json={"id": check_id})
        if p.startswith("/repos/o/r/check-runs/") and req.method == "PATCH":
            if self.fail_interrupted_update and body.get("conclusion") == "action_required":
                return httpx.Response(503, json={"message": "GitHub unavailable during cleanup"})
            check_id = int(p.rsplit("/", 1)[1])
            next(cr for cr in self.check_runs if cr["id"] == check_id).update(body)
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"message": f"unexpected {req.method} {p}"})


def _app(fake):
    return GitHubApp(app_id="123", private_key_pem=KEY, transport=httpx.MockTransport(fake))


@pytest.fixture
def stub_work(monkeypatch, tmp_path):
    async def fetch(full_name, sha, token, dest):
        assert token == "t-scoped"
        dest.mkdir(parents=True)
        (dest / "app.py").write_text("x = 1\n" if sha.startswith("b") else "x = 2\n")
        return dest

    monkeypatch.setattr(flows, "fetch_revision", fetch)
    monkeypatch.setattr(flows, "prepare", lambda b, h: (tmp_path / "work", b, h))
    return monkeypatch


SUITE = [SuiteItem("unit:tests/test_x.py", "unit", ["component:*"], {"code"}, always=True)]
IDENTITY = flows.guard_identity(
    "o/r", 5, {"base_sha": "b" * 40, "head_sha": "h" * 40}, SUITE, None, ["q"], None
)


async def test_guard_pr_reports_a_check_run(stub_work):
    stub_work.setattr(
        flows,
        "run_items",
        lambda items, ctx, progress, on_event=None: [
            ItemResult("unit:tests/test_x.py", "fail", "1 failed")
        ],
    )
    fake = FakeGitHub()
    out = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert out["conclusion"] == "failure" and out["check_id"] == 991
    token_req = next(b for m, p, b in fake.calls if p.endswith("/access_tokens"))
    assert token_req == {"repositories": ["r"], "permissions": GUARD_PERMISSIONS}
    create = next(b for m, p, b in fake.calls if p == "/repos/o/r/check-runs")
    assert create["head_sha"] == "h" * 40 and create["status"] == "in_progress"
    done = next(b for m, p, b in fake.calls if m == "PATCH")
    assert done["conclusion"] == "failure" and "regression" in done["output"]["title"]
    # read-only flow: nothing but the check run is written
    writes = [(m, p) for m, p, _ in fake.calls if m in ("POST", "PATCH", "PUT", "DELETE")]
    assert {p for _, p in writes} <= {
        "/app/installations/77/access_tokens",
        "/repos/o/r/check-runs",
        "/repos/o/r/check-runs/991",
    }


async def test_guard_pr_streams_impact_then_checks_then_verdict(stub_work):
    def run(items, ctx, progress, on_event=None):
        assert on_event is not None
        on_event({"type": "check_start", "key": items[0].key, "kind": "unit"})
        on_event({"type": "check_done", "key": items[0].key, "verdict": "pass", "seconds": 0.1})
        return [ItemResult(items[0].key, "pass", "ok")]

    stub_work.setattr(flows, "run_items", run)
    events: list[dict] = []
    out = await flows.guard_pr(
        _app(FakeGitHub()), "o/r", 5, suite=SUITE, target=None, questions=["q"],
        on_event=events.append,
    )  # fmt: skip
    assert [e["type"] for e in events] == ["impact", "check_start", "check_done", "verdict"]
    impact = events[0]
    assert impact["changed"] == ["app.py"] and impact["full_suite_size"] == 1
    assert [s["key"] for s in impact["selected"]] == ["unit:tests/test_x.py"]
    assert events[-1]["conclusion"] == out["conclusion"] == "success"


async def test_guard_pr_crash_still_completes_the_check(stub_work):
    def boom(items, ctx, progress, on_event=None):
        raise RuntimeError("sandbox unavailable")

    stub_work.setattr(flows, "run_items", boom)
    fake = FakeGitHub()
    with pytest.raises(RuntimeError):
        await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    done = next(b for m, p, b in fake.calls if m == "PATCH")
    assert (
        done["conclusion"] == "action_required"
        and "sandbox unavailable" in done["output"]["summary"]
    )


def _writes(fake):
    return [(m, p) for m, p, _ in fake.calls if m in ("POST", "PATCH", "PUT", "DELETE")]


def _passing(items, ctx, progress, on_event=None):
    return [ItemResult(items[0].key, "pass", "ok")]


@pytest.mark.parametrize("recovered_verdict", ["pass", "fail"])
@pytest.mark.parametrize("cancelled", [False, True])
async def test_guard_retry_executes_checks_after_an_incomplete_attempt(
    stub_work, cancelled, recovered_verdict
):
    """Exercise the persisted GitHub state across a failed attempt and its retry."""
    import asyncio

    calls = 0

    def run(items, ctx, progress, on_event=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            if cancelled:
                raise asyncio.CancelledError()
            raise RuntimeError("sandbox unavailable")
        return [ItemResult(items[0].key, recovered_verdict, "recovered")]

    stub_work.setattr(flows, "run_items", run)
    fake = FakeGitHub()
    error = asyncio.CancelledError if cancelled else RuntimeError
    with pytest.raises(error):
        await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])

    out = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert calls == 2  # before the fix: 1; the retry just returned the neutral error
    assert out["conclusion"] == ("success" if recovered_verdict == "pass" else "failure")
    assert not out.get("reused")
    assert fake.check_runs[1]["conclusion"] == "action_required"
    assert len(fake.check_runs) == 2  # retain the failed attempt's diagnostic record
    again = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert again["reused"] and again["check_id"] == out["check_id"]
    assert calls == 2 and len(fake.check_runs) == 2


@pytest.mark.parametrize(
    "status,conclusion",
    [
        ("completed", "neutral"),
        ("completed", "success"),
        ("in_progress", None),
    ],
)
async def test_guard_reevaluates_unidentified_legacy_check_once(stub_work, status, conclusion):
    calls = 0

    def run(*args):
        nonlocal calls
        calls += 1
        return _passing(*args)

    stub_work.setattr(flows, "run_items", run)
    fake = FakeGitHub(
        check_runs=[
            {
                "id": 55,
                "status": status,
                "conclusion": conclusion,
                "output": {"title": "Furnace Guard could not complete"},
            }
        ]
    )
    out = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert out["conclusion"] == "success" and not out.get("reused")
    again = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert again["reused"] and again["check_id"] == out["check_id"]
    assert calls == 1 and len(fake.check_runs) == 2


@pytest.mark.db
@pytest.mark.parametrize("recovers", [False, True])
@pytest.mark.parametrize("failure_mode", ["error", "timeout"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_worker_retries_guard_and_honors_attempt_limit(
    clean_jobs, stub_work, recovers, failure_mode, cleanup_fails
):
    """Real queue -> worker -> GitHub handler -> flow, with only GitHub/work mocked."""
    from datetime import UTC, datetime

    from furnace.db.models import Job
    from furnace.db.session import session_scope
    from furnace.github import jobs as gh_jobs
    from furnace.jobs import queue, worker
    from sqlalchemy import update

    fake = FakeGitHub()
    fake.fail_interrupted_update = cleanup_fails
    stub_work.setattr(gh_jobs, "_runner_config", lambda: (_app(fake), SUITE, ["q"]))
    calls = 0
    fetches = 0
    original_fetch = flows.fetch_revision

    async def fetch(*args):
        import asyncio

        nonlocal fetches
        fetches += 1
        if failure_mode == "timeout" and (fetches == 1 or not recovers):
            await asyncio.sleep(30)  # cancelled by the worker's real per-job timeout
        return await original_fetch(*args)

    stub_work.setattr(flows, "fetch_revision", fetch)

    def run(items, ctx, progress, on_event=None):
        nonlocal calls
        calls += 1
        if failure_mode == "error" and (calls == 1 or not recovers):
            raise RuntimeError("sandbox unavailable")
        return _passing(items, ctx, progress, on_event)

    stub_work.setattr(flows, "run_items", run)
    async with session_scope() as s:
        job = await queue.enqueue(
            s,
            queue="runner",
            kind="guard.pr",
            max_attempts=2,
            payload={"repo": "o/r", "number": 5, "head_sha": "h" * 40, "installation_id": 77},
        )
        job.timeout_s = 1 if failure_mode == "timeout" else 30
        job_id = job.id
    assert await worker.run_one("retry-test", ["runner"])
    async with session_scope() as s:
        first = await s.get(Job, job_id)
        assert first is not None and first.status == "queued" and first.attempts == 1
        assert first.error is not None
        assert first.result is None
        assert ("timed out" if failure_mode == "timeout" else "sandbox unavailable") in first.error
        # The backoff itself is tested by test_jobs_queue; make the retry due now.
        await s.execute(update(Job).where(Job.id == job_id).values(run_after=datetime.now(UTC)))
    assert await worker.run_one("retry-test", ["runner"])
    async with session_scope() as s:
        final = await s.get(Job, job_id)
        assert final is not None and final.attempts == 2
        assert final.status == ("succeeded" if recovers else "failed")
        if recovers:
            assert final.result is not None
            assert final.result["conclusion"] == "success"
        else:
            assert final.result is None
    assert calls == (2 if failure_mode == "error" else int(recovers))
    assert len(fake.check_runs) == (1 if cleanup_fails else 2)
    assert fake.check_runs[0].get("conclusion") == (
        "success" if recovers else (None if cleanup_fails else "action_required")
    )
    assert not await worker.run_one("retry-test", ["runner"])


@pytest.mark.parametrize("conclusion", ["success", "failure", "neutral"])
async def test_guard_pr_returns_a_completed_check_instead_of_running_again(stub_work, conclusion):
    """A retried job or a second event for the same head commit must not post a second
    check run (or spend two minutes of GPU on the same answer)."""
    stub_work.setattr(flows, "run_items", lambda *a, **k: pytest.fail("checks must not run"))
    done = {
        "id": 55,
        "external_id": IDENTITY,
        "status": "completed",
        "conclusion": conclusion,
        "output": {"title": "p95 +900%"},
    }
    fake = FakeGitHub(check_runs=[done])
    out = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert out["reused"] and out["check_id"] == 55 and out["conclusion"] == conclusion
    assert _writes(fake) == [("POST", "/app/installations/77/access_tokens")]


@pytest.mark.parametrize("change", ["base", "pr", "suite", "questions", "target", "budget"])
async def test_completed_check_is_reused_only_for_same_evaluation(stub_work, change):
    from furnace_bench.schema import BenchTarget

    calls = 0

    def run(*args):
        nonlocal calls
        calls += 1
        return _passing(*args)

    stub_work.setattr(flows, "run_items", run)
    fake = FakeGitHub()
    kwargs: dict = {"suite": SUITE, "target": None, "questions": ["q"]}
    first = await flows.guard_pr(_app(fake), "o/r", 5, **kwargs)
    number = 5
    if change == "base":
        fake.base_sha = "a" * 40
    elif change == "pr":
        number = 6
    elif change == "suite":
        kwargs["suite"] = [SuiteItem("unit:other", "unit", [], set(), always=True)]
    elif change == "questions":
        kwargs["questions"] = ["different"]
    elif change == "target":
        kwargs["target"] = BenchTarget(base_url="http://localhost:8100/v1", model="other")
    else:
        kwargs["max_prompt_tokens"] = 4096
    second = await flows.guard_pr(_app(fake), "o/r", number, **kwargs)
    assert calls == 2 and second["check_id"] != first["check_id"]
    again = await flows.guard_pr(_app(fake), "o/r", number, **kwargs)
    assert again["reused"] and again["check_id"] == second["check_id"] and calls == 2
    # Returning to the first identity must find it behind a newer, unrelated check.
    fake.base_sha = "b" * 40
    original = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert original["reused"] and original["check_id"] == first["check_id"]
    assert calls == 2 and len(fake.check_runs) == 2


async def test_guard_pr_takes_over_an_abandoned_check_and_reruns_on_request(stub_work):
    stub_work.setattr(flows, "run_items", _passing)
    # an attempt that died left its check run in progress: the retry finishes *that* run
    fake = FakeGitHub(
        check_runs=[
            {
                "id": 991,
                "status": "in_progress",
                "conclusion": None,
                "external_id": IDENTITY,
            }
        ]
    )
    out = await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert out["check_id"] == 991 and out["conclusion"] == "success"
    assert ("POST", "/repos/o/r/check-runs") not in _writes(fake)
    # an explicit re-run creates a new one even though a completed run exists
    fake = FakeGitHub(check_runs=[{"id": 55, "status": "completed", "conclusion": "failure"}])
    out = await flows.guard_pr(
        _app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"], rerun=True
    )
    assert out["check_id"] == 991 and ("POST", "/repos/o/r/check-runs") in _writes(fake)


async def test_guard_pr_skips_a_superseded_head(stub_work):
    fake = FakeGitHub()
    out = await flows.guard_pr(
        _app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"],
        expected_head_sha="a" * 40,
    )  # fmt: skip
    assert out["superseded"] and out["conclusion"] == "skipped"
    assert not any("/check-runs" in p for _, p in _writes(fake))


@pytest.mark.adversarial
async def test_guard_pr_refuses_to_act_under_another_installation(stub_work):
    fake = FakeGitHub()
    with pytest.raises(GitHubError, match="across installations"):
        await flows.guard_pr(
            _app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"],
            expected_installation=78,
        )  # fmt: skip
    assert not any(p.endswith("/access_tokens") for _, p, _ in fake.calls)  # no token minted


@pytest.mark.adversarial
async def test_guard_pr_cancelled_mid_run_still_completes_the_check(stub_work):
    """A job timeout or a lost lease cancels the coroutine; the check must not keep spinning."""
    import asyncio

    started = asyncio.Event()

    async def hanging_to_thread(fn, *args, **kw):  # analyze_tree "takes forever"
        started.set()
        await asyncio.sleep(30)

    stub_work.setattr(flows.asyncio, "to_thread", hanging_to_thread)
    fake = FakeGitHub()
    task = asyncio.create_task(
        flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    )
    await asyncio.wait_for(started.wait(), 10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    done = next(b for m, p, b in fake.calls if m == "PATCH")
    assert done["conclusion"] == "action_required" and "cancelled" in done["output"]["summary"]


@pytest.mark.adversarial
async def test_fork_pull_requests_are_refused(stub_work):
    fake = FakeGitHub(head_repo="stranger/r")
    with pytest.raises(GitHubError, match="fork"):
        await flows.guard_pr(_app(fake), "o/r", 5, suite=SUITE, target=None, questions=["q"])
    assert not any(p.endswith("/check-runs") for _, p, _ in fake.calls)


async def test_app_not_installed_is_a_clear_error():
    def nothing(req):
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(GitHubError, match="not installed on o/r"):
        await GitHubApp(
            app_id="1", private_key_pem=KEY, transport=httpx.MockTransport(nothing)
        ).installation_for("o/r")


def test_cli_loads_suite_and_questions(tmp_path):
    from furnace import cli

    suite_file = tmp_path / "s.py"
    suite_file.write_text(
        "from furnace.guardian.impact import SuiteItem\nF1_SUITE = [SuiteItem('a', 'unit', [], set())]\n"
    )
    assert [i.key for i in cli._suite(str(suite_file))] == ["a"]
    qf = tmp_path / "q.json"
    qf.write_text(json.dumps([{"question": "one?"}, "two?"]))
    assert cli._questions(str(qf)) == ["one?", "two?"]
    assert cli._questions(None) == cli.DEFAULT_QUESTIONS
