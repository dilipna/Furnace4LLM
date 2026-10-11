"""Turning GitHub webhook events into runner jobs, exactly once.

Both ways an event reaches Furnace go through `ingest`:
  * push: GitHub POSTs to the API's /api/github/webhook (HMAC-verified there);
  * poll: the laptop runner reads the App's own delivery log over the authenticated
    GitHub API (furnace.github.deliveries), for setups without a public URL.

Guarantees, each covered by a test:
  * a delivery GUID is processed at most once (webhook_deliveries primary key). GitHub
    keeps the GUID when it redelivers, so a redelivery, a replayed capture of a signed
    request, or the same event seen by both push and poll never enqueues twice (a human
    re-runs Guard deliberately with `furnace gh-guard`, which runs again by default);
  * at most one active Guard job per PR head commit (job dedupe key): distinct events
    for the same commit ("opened" then "ready_for_review") attach to the one active job,
    and the runner reuses the check run per head commit (furnace.github.flows.guard_pr);
  * payloads are validated before use: malformed events are rejected, not half-processed;
  * every delivery leaves an audit row with what was decided and why.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from furnace.db.models import WebhookDelivery
from furnace.jobs import queue

GUARD_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}
GUARD_TIMEOUT_S = 1800
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DELIVERY_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class InvalidEvent(ValueError):
    """The payload does not have the shape GitHub sends; nothing was recorded."""


@dataclass
class PullRequestEvent:
    repo: str
    number: int
    head_sha: str
    head_repo: str | None
    draft: bool
    installation_id: int | None


def _parse_pull_request(payload: dict[str, Any]) -> PullRequestEvent:
    try:
        pr = payload["pull_request"]
        repo = payload["repository"]["full_name"]
        number = pr["number"]
        head_sha = pr["head"]["sha"]
        head_repo = (pr["head"].get("repo") or {}).get("full_name")
    except (KeyError, TypeError, AttributeError) as exc:
        raise InvalidEvent(f"pull_request event missing {exc}") from exc
    if not isinstance(repo, str) or not REPO_RE.match(repo):
        raise InvalidEvent("repository.full_name is not owner/name")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise InvalidEvent("pull_request.number is not a positive integer")
    if not isinstance(head_sha, str) or not SHA_RE.match(head_sha):
        raise InvalidEvent("pull_request.head.sha is not a 40-hex commit id")
    inst = (payload.get("installation") or {}).get("id")
    if inst is not None and (not isinstance(inst, int) or isinstance(inst, bool)):
        raise InvalidEvent("installation.id is not an integer")
    return PullRequestEvent(
        repo=repo,
        number=number,
        head_sha=head_sha,
        head_repo=head_repo if isinstance(head_repo, str) else None,
        draft=bool(pr.get("draft")),
        installation_id=inst,
    )


def guard_dedupe_key(repo: str, number: int, head_sha: str) -> str:
    return f"guard.pr:{repo}#{number}@{head_sha}"


def repair_dedupe_key(repo: str, number: int, head_sha: str) -> str:
    return f"repair.pr:{repo}#{number}@{head_sha}"


def allowed_repos(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {r.strip().lower() for r in raw.split(",") if r.strip()}


async def ingest(
    session: AsyncSession,
    *,
    delivery_id: str,
    event: str,
    payload: dict[str, Any],
    source: str = "push",
    allowed: set[str] | None = None,
) -> dict[str, Any]:
    """Record the delivery and decide. Returns {queued, reason, job_id?, duplicate?}.
    Raises InvalidEvent for a malformed delivery id or payload (nothing recorded)."""
    if not DELIVERY_RE.match(delivery_id or ""):
        raise InvalidEvent("missing or malformed X-GitHub-Delivery")
    if not isinstance(payload, dict):
        raise InvalidEvent("payload is not a JSON object")
    action = payload.get("action") if isinstance(payload.get("action"), str) else None
    parsed = _parse_pull_request(payload) if event == "pull_request" else None
    repo = parsed.repo if parsed else (payload.get("repository") or {}).get("full_name")
    inst = parsed.installation_id if parsed else (payload.get("installation") or {}).get("id")

    inserted = (
        await session.execute(
            insert(WebhookDelivery)
            .values(
                delivery_id=delivery_id,
                event=event[:50],
                action=action,
                repo=repo if isinstance(repo, str) else None,
                installation_id=inst if isinstance(inst, int) else None,
                source=source,
            )
            .on_conflict_do_nothing(index_elements=[WebhookDelivery.delivery_id])
            .returning(WebhookDelivery.delivery_id)
        )
    ).scalar_one_or_none()
    if inserted is None:
        return {
            "queued": False,
            "duplicate": True,
            "reason": "duplicate delivery (already processed)",
        }

    decision = _decide(event, action, parsed, allowed)
    job_id = None
    outcome = "ignored"
    if decision is None and parsed is not None:
        job, created = await queue.enqueue_once(
            session,
            queue="runner",
            kind="guard.pr",
            dedupe_key=guard_dedupe_key(parsed.repo, parsed.number, parsed.head_sha),
            payload={
                "repo": parsed.repo,
                "number": parsed.number,
                "head_sha": parsed.head_sha,
                "installation_id": parsed.installation_id,
                "delivery_id": delivery_id,
            },
            max_attempts=2,
            timeout_s=GUARD_TIMEOUT_S,
        )
        job_id = job.id
        outcome = "queued" if created else "duplicate_job"
        decision = None if created else f"attached to active job {job.id} for this PR head"
    await session.execute(
        update(WebhookDelivery)
        .where(WebhookDelivery.delivery_id == delivery_id)
        .values(outcome=outcome, detail=decision, job_id=job_id)
    )
    out: dict[str, Any] = {"queued": outcome == "queued", "reason": decision or "queued"}
    if job_id is not None:
        out["job_id"] = str(job_id)
    return out


def _decide(
    event: str, action: str | None, pr: PullRequestEvent | None, allowed: set[str] | None
) -> str | None:
    """None = enqueue Guard; otherwise the reason the event is ignored."""
    if event == "ping":
        return "ping"
    if event != "pull_request" or pr is None or action not in GUARD_ACTIONS:
        return f"ignored {event}/{action}"
    if allowed is not None and pr.repo.lower() not in allowed:
        return f"repository {pr.repo} is not in FURNACE_GITHUB_ALLOWED_REPOS"
    if pr.head_repo != pr.repo:
        return "pull request from a fork (its code would run in the sandbox)"
    if pr.draft and action != "ready_for_review":
        return "draft pull request"
    return None
