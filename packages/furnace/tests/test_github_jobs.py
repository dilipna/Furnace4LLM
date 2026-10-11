"""Runner jobs for GitHub events: Guard -> repair chaining needs explicit consent, enqueues at
most one repair per PR head, and bad runner configuration fails the job, not the worker."""

import pytest
from furnace.db.models import Job
from furnace.db.session import session_scope
from furnace.github import flows
from furnace.github import jobs as gh_jobs
from furnace.jobs import queue
from furnace.jobs.worker import JobContext
from furnace.settings import get_settings
from sqlalchemy import select

pytestmark = pytest.mark.db
HEAD = "c" * 40


async def _guard_ctx() -> JobContext:
    async with session_scope() as s:
        job = await queue.enqueue(
            s,
            queue="runner",
            kind="guard.pr",
            payload={"repo": "o/r", "number": 3, "head_sha": HEAD, "installation_id": 9},
        )
    return JobContext(job)


@pytest.fixture
def guard_fails(monkeypatch):
    seen: dict = {}

    async def fake_guard_pr(app, repo, number, **kw):
        seen.update(kw)
        return {
            "check_id": 1,
            "conclusion": "failure",
            "title": "p95 TTFT +900%",
            "signatures": ["prefix_instability"],
        }

    monkeypatch.setattr(flows, "guard_pr", fake_guard_pr)
    monkeypatch.setattr(gh_jobs, "_runner_config", lambda: (object(), [], ["q"]))
    yield seen
    get_settings.cache_clear()


async def _repair_jobs() -> list[Job]:
    async with session_scope() as s:
        return list((await s.execute(select(Job).where(Job.kind == "repair.pr"))).scalars())


async def test_guard_failure_does_not_repair_without_consent(clean_jobs, guard_fails, monkeypatch):
    monkeypatch.delenv("FURNACE_GUARD_AUTO_REPAIR", raising=False)
    get_settings.cache_clear()
    out = await gh_jobs.guard_pull_request(await _guard_ctx())
    assert out is not None
    assert out["repair"] == {"enqueued": False, "reason": "FURNACE_GUARD_AUTO_REPAIR is off"}
    assert await _repair_jobs() == []
    # the job passes the event's head and installation through, for the runner to verify
    assert guard_fails["expected_head_sha"] == HEAD and guard_fails["expected_installation"] == 9


async def test_guard_failure_with_consent_enqueues_one_repair_per_head(
    clean_jobs, guard_fails, monkeypatch
):
    monkeypatch.setenv("FURNACE_GUARD_AUTO_REPAIR", "true")
    get_settings.cache_clear()
    first = await gh_jobs.guard_pull_request(await _guard_ctx())
    second = await gh_jobs.guard_pull_request(await _guard_ctx())  # retried guard job
    assert first is not None and second is not None
    assert first["repair"]["enqueued"] is True and second["repair"]["enqueued"] is False
    rj = await _repair_jobs()
    assert len(rj) == 1 and rj[0].payload["head_sha"] == HEAD
    assert rj[0].payload["installation_id"] == 9 and rj[0].max_attempts == 1


async def test_guard_success_or_unsupported_failure_never_repairs(clean_jobs, monkeypatch):
    monkeypatch.setenv("FURNACE_GUARD_AUTO_REPAIR", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(gh_jobs, "_runner_config", lambda: (object(), [], ["q"]))
    for conclusion, sigs in (("success", ["prefix_instability"]), ("failure", [])):

        async def fake(app, repo, number, _c=conclusion, _s=sigs, **kw):
            return {"check_id": 1, "conclusion": _c, "title": "t", "signatures": _s}

        monkeypatch.setattr(flows, "guard_pr", fake)
        out = await gh_jobs.guard_pull_request(await _guard_ctx())
        assert out is not None and "repair" not in out
    assert await _repair_jobs() == []
    get_settings.cache_clear()


async def test_bad_runner_configuration_fails_the_job_not_the_worker(monkeypatch, tmp_path):
    """The CLI helpers raise SystemExit; inside the runner that would end the process."""
    from furnace import cli

    monkeypatch.setenv("FURNACE_GUARD_SUITE_PATH", str(tmp_path / "suite.py"))
    get_settings.cache_clear()

    def no_app():
        raise SystemExit("set FURNACE_GITHUB_APP_ID")

    monkeypatch.setattr(cli, "_app", no_app)
    with pytest.raises(RuntimeError, match="runner configuration: set FURNACE_GITHUB_APP_ID"):
        gh_jobs._runner_config()
    get_settings.cache_clear()


def test_supported_signatures_come_from_the_impact_graph():
    from furnace.contracts.guard import PRImpact, TouchedNode, TouchVia
    from furnace.guardian.impact import ImpactResult
    from furnace.guardian.repair.signatures import supported_signatures

    def impact(change):
        t = TouchedNode(
            node_key="prompt:app/prompts.py::build#system",
            via=TouchVia.prompt_segment,
            attr_changes={"dynamic_head": change},
        )
        return ImpactResult(
            impact=PRImpact(pr_number=1, base_sha="b", head_sha="h", touched=[t]),
            categories=set(),
            affected_paths={},
        )

    assert supported_signatures(impact((False, True))) == ["prefix_instability"]
    assert supported_signatures(impact([False, True])) == ["prefix_instability"]  # from JSON
    assert supported_signatures(impact((True, False))) == []  # a fix, not a regression
    assert supported_signatures(impact((True, True))) == []
