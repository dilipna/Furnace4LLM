import httpx

from app.config import TICKETS_URL


class ApprovalRequired(Exception):
    pass


def create_ticket(summary: str, email: str, approved: bool) -> dict:
    """Open a support ticket in the helpdesk. Requires explicit user approval."""
    if not approved:
        raise ApprovalRequired("ticket creation requires user confirmation")
    resp = httpx.post(TICKETS_URL, json={"summary": summary, "email": email}, timeout=10)
    resp.raise_for_status()
    return resp.json()
