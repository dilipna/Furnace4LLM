"""Live Guard runs API: start rules (known scenario, runner online, one at a time) and the
job-event stream a live view replays."""

import asyncio
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from furnace.db.models import Job, Runner
from furnace.db.session import session_scope
from furnace.jobs import queue
from furnace_api.main import app
from furnace_api.routers import guard_runs
from sqlalchemy import delete, update

pytestmark = pytest.mark.db


def _run(coro):
    return asyncio.run(coro)


async def _reset(runner_online: bool):
    async with session_scope() as s:
        await s.execute(
            update(Job)
            .where(Job.kind.in_(guard_runs.GUARD_KINDS), Job.status.in_(("queued", "running")))
            .values(status="failed", error="test reset")
        )
        await s.execute(delete(Runner).where(Runner.id == "test-guard-runner"))
        if runner_online:
            s.add(Runner(id="test-guard-runner", queues=["runner"], capabilities={},
                         last_seen=datetime.now(UTC)))  # fmt: skip


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(guard_runs, "_RATE", guard_runs.defaultdict(guard_runs.deque))
    with TestClient(app) as c:
        yield c
    _run(_reset(False))


def test_start_requires_known_scenario_and_online_runner(client):
    _run(_reset(False))
    assert client.post("/api/guard/runs", json={"scenario": "no_such_pr"}).status_code == 404
    assert client.post("/api/guard/runs", json={"scenario": "../etc"}).status_code == 422
    r = client.post("/api/guard/runs", json={"scenario": "r1_dynamic_head"})
    assert r.status_code == 503 and "runner" in r.json()["detail"]


def test_one_run_at_a_time_then_stream_its_events(client):
    _run(_reset(True))
    r = client.post("/api/guard/runs", json={"scenario": "r1_dynamic_head"})
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]
    busy = client.post("/api/guard/runs", json={"scenario": "r1_dynamic_head"})
    assert busy.status_code == 409 and busy.json()["detail"]["job_id"] == job_id
    latest = client.get("/api/guard/runs/latest", params={"scenario": "r1_dynamic_head"}).json()
    assert latest["job_id"] == job_id and latest["status"] == "queued"

    async def work():
        import uuid

        jid = uuid.UUID(job_id)
        async with session_scope() as s:
            await queue.emit(s, jid, "guard", "impact", data={"type": "impact", "touched": []})
            await queue.emit(
                s, jid, "guard", "x: running", data={"type": "check_start", "key": "x"}
            )
            await queue.complete(s, jid, {"conclusion": "success"})

    _run(work())
    text = client.get(f"/api/guard/runs/{job_id}/events").text
    datas = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]
    assert [d["data"]["type"] for d in datas[:2]] == ["impact", "check_start"]
    assert datas[-1]["status"] == "succeeded"
    # resume after the first event
    first_id = next(line[4:] for line in text.splitlines() if line.startswith("id: "))
    tail = client.get(f"/api/guard/runs/{job_id}/events", headers={"Last-Event-ID": first_id}).text
    assert '"check_start"' in tail and '"impact"' not in tail


def test_events_only_for_guard_jobs(client):
    async def other():
        async with session_scope() as s:
            j = await queue.enqueue(s, queue="cpu", kind="system.ping")
            return str(j.id)

    jid = _run(other())
    assert client.get(f"/api/guard/runs/{jid}/events").status_code == 404
    assert client.get("/api/guard/runs/not-a-uuid/events").status_code == 404
