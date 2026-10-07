"""GitHub webhook receiver: verified pull_request events become `guard.pr` runner jobs."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from furnace.github.client import verify_webhook
from furnace.jobs import queue
from furnace.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession

from furnace_api.deps import db_session

router = APIRouter(prefix="/api/github")
DB = Annotated[AsyncSession, Depends(db_session)]
GUARD_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


@router.post("/webhook", status_code=202)
async def webhook(
    request: Request,
    db: DB,
    x_github_event: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    secret = get_settings().github_webhook_secret
    if secret is None:
        raise HTTPException(503, "webhooks are not configured on this deployment")
    body = await request.body()
    if not verify_webhook(secret.get_secret_value(), body, x_hub_signature_256):
        raise HTTPException(401, "invalid signature")
    event = json.loads(body)
    if x_github_event == "ping":
        return {"queued": False, "reason": "ping"}
    if x_github_event != "pull_request" or event.get("action") not in GUARD_ACTIONS:
        return {"queued": False, "reason": f"ignored {x_github_event}/{event.get('action')}"}
    pr = event["pull_request"]
    repo = event["repository"]["full_name"]
    if (pr["head"].get("repo") or {}).get("full_name") != repo:
        return {"queued": False, "reason": "pull request from a fork"}
    if pr.get("draft") and event["action"] != "ready_for_review":
        return {"queued": False, "reason": "draft pull request"}
    job = await queue.enqueue(
        db,
        queue="runner",
        kind="guard.pr",
        payload={"repo": repo, "number": pr["number"], "head_sha": pr["head"]["sha"]},
        max_attempts=1,
    )
    return {"queued": True, "job_id": str(job.id)}
