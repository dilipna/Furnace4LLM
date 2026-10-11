"""Pull-mode webhooks (`furnace gh-poll`): read the GitHub App's own delivery log.

GitHub records every webhook delivery it attempts for an App, with the full payload,
whether or not the receiving URL answered. This poller lists those deliveries
(GET /app/hook/deliveries) and fetches each new one (GET /app/hook/deliveries/{id}),
authenticated as the App (RS256 JWT over TLS to api.github.com), then hands it to the
same `ingest` the HTTPS endpoint uses. So a laptop runner receives the real events
without a public URL.

Trust: authenticity comes from fetching from GitHub's API with the App's own credentials,
not from the HMAC signature (GitHub returns the payload re-serialized, so the signature
cannot be recomputed). Exactly-once: the delivery GUID is the dedupe key in both paths, so
running push and poll together is safe. Only deliveries newer than the poller's start
minus `lookback` are considered, so starting it does not replay old history.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from furnace.github.client import API, HEADERS, GitHubApp, GitHubError, app_jwt

log = logging.getLogger("furnace.github.deliveries")
Ingest = Callable[[str, str, dict[str, Any]], Awaitable[dict[str, Any]]]
Known = Callable[[list[str]], Awaitable[set[str]]]


class DeliveryLog:
    def __init__(self, app: GitHubApp) -> None:
        self.app = app

    def _client(self) -> httpx.AsyncClient:
        jwt = app_jwt(self.app.app_id, self.app.private_key_pem)
        return httpx.AsyncClient(
            base_url=API,
            headers={**HEADERS, "Authorization": f"Bearer {jwt}"},
            transport=self.app.transport,
            timeout=20,
        )

    async def recent(self, per_page: int = 50) -> list[dict[str, Any]]:
        async with self._client() as c:
            r = await c.get("/app/hook/deliveries", params={"per_page": per_page})
        if r.status_code != 200:
            raise GitHubError(f"GET /app/hook/deliveries: {r.status_code} {r.text[:200]}")
        return r.json()

    async def payload(self, delivery_id: int) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(f"/app/hook/deliveries/{delivery_id}")
        if r.status_code != 200:
            raise GitHubError(f"GET /app/hook/deliveries/{delivery_id}: {r.status_code}")
        payload = (r.json().get("request") or {}).get("payload")
        if isinstance(payload, str):  # some deliveries carry the raw JSON text
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise GitHubError(f"delivery {delivery_id} has no JSON payload")
        return payload


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


async def poll_once(
    log_: DeliveryLog,
    ingest: Ingest,
    known: Known,
    since: datetime,
    rejected: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Ingest every delivery newer than `since` whose GUID is not processed yet. Returns
    one record per ingested delivery. Redeliveries share the GUID and are skipped. A
    delivery whose payload is rejected is reported once and remembered in `rejected`."""
    from furnace.github.events import InvalidEvent

    rejected = rejected if rejected is not None else set()
    items = await log_.recent()
    fresh: dict[str, dict[str, Any]] = {}
    for d in items:
        ts = _parse_ts(d.get("delivered_at"))
        guid = d.get("guid")
        if not guid or ts is None or ts < since:
            continue
        fresh.setdefault(guid, d)  # newest first; keep one delivery per GUID
    if not fresh:
        return []
    seen = await known(list(fresh))
    out = []
    for guid, d in sorted(fresh.items(), key=lambda kv: kv[1]["delivered_at"]):
        if guid in seen or guid in rejected:
            continue
        try:
            payload = await log_.payload(int(d["id"]))
            res = await ingest(guid, str(d.get("event") or ""), payload)
        except (InvalidEvent, ValueError, GitHubError) as exc:
            rejected.add(guid)
            res = {"queued": False, "reason": f"rejected: {exc}"}
        out.append({"guid": guid, "event": d.get("event"), "action": d.get("action"), **res})
    return out


async def run(
    app: GitHubApp,
    *,
    interval_s: float = 10.0,
    lookback: timedelta = timedelta(minutes=10),
    once: bool = False,
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    from sqlalchemy import select

    from furnace.db.models import WebhookDelivery
    from furnace.db.session import session_scope
    from furnace.github.events import allowed_repos, ingest
    from furnace.settings import get_settings

    allowed = allowed_repos(get_settings().github_allowed_repos)

    async def do_ingest(guid: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with session_scope() as s:
            return await ingest(
                s, delivery_id=guid, event=event, payload=payload, source="poll", allowed=allowed
            )

    async def known(guids: list[str]) -> set[str]:
        async with session_scope() as s:
            rows = await s.execute(
                select(WebhookDelivery.delivery_id).where(WebhookDelivery.delivery_id.in_(guids))
            )
            return set(rows.scalars())

    since = datetime.now(UTC) - lookback
    dlog = DeliveryLog(app)
    rejected: set[str] = set()
    while True:
        try:
            for rec in await poll_once(dlog, do_ingest, known, since, rejected):
                if on_result:
                    on_result(rec)
        except (GitHubError, httpx.HTTPError) as exc:  # transient: report, keep polling
            log.warning("delivery poll failed: %s", exc)
            if once:
                raise
        if once:
            return
        await asyncio.sleep(interval_s)
