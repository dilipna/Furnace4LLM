"""GitHub webhook receiver: verified pull_request events become `guard.pr` runner jobs.

The endpoint authenticates (HMAC over the raw body), bounds and parses the payload, then
hands it to furnace.github.events.ingest, which records the delivery exactly once and
enqueues at most one Guard job per PR head commit. It never runs repository code.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from furnace.github.client import verify_webhook
from furnace.github.events import InvalidEvent, allowed_repos, ingest
from furnace.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession

from furnace_api.deps import db_session

router = APIRouter(prefix="/api/github")
DB = Annotated[AsyncSession, Depends(db_session)]
MAX_BODY_BYTES = 5 * 1024 * 1024  # pull_request payloads are tens of KB; GitHub caps at 25 MB


@router.post("/webhook", status_code=202)
async def webhook(
    request: Request,
    db: DB,
    x_github_event: Annotated[str | None, Header()] = None,
    x_github_delivery: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.github_webhook_secret
    if secret is None:
        raise HTTPException(503, "webhooks are not configured on this deployment")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(413, "payload too large")
    if not verify_webhook(secret.get_secret_value(), body, x_hub_signature_256):
        raise HTTPException(401, "invalid signature")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "body is not JSON") from exc
    try:
        return await ingest(
            db,
            delivery_id=x_github_delivery or "",
            event=x_github_event or "",
            payload=payload,
            source="push",
            allowed=allowed_repos(settings.github_allowed_repos),
        )
    except InvalidEvent as exc:
        raise HTTPException(400, str(exc)) from exc
