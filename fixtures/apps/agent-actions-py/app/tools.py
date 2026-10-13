import json
from pathlib import Path

import httpx

from app.config import EMAIL_URL, PAYMENTS_URL

ORDERS = Path(__file__).resolve().parent.parent / "data" / "orders.json"


class ApprovalRequired(Exception):
    pass


def search_orders(customer_email: str) -> list[dict]:
    """Return the customer's orders (read-only)."""
    orders = json.loads(ORDERS.read_text(encoding="utf-8"))
    return [o for o in orders if o["email"] == customer_email]


def issue_refund(order_id: str, amount: float, approved: bool) -> dict:
    """Refund an order through the payments service. Requires the customer's confirmation."""
    if not approved:
        raise ApprovalRequired("a refund requires the customer's confirmation")
    resp = httpx.post(PAYMENTS_URL, json={"order_id": order_id, "amount": amount}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email to the customer through the mailer service."""
    resp = httpx.post(EMAIL_URL, json={"to": to, "subject": subject, "body": body}, timeout=10)
    resp.raise_for_status()
    return resp.json()


TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_orders",
            "description": "Look up a customer's orders by email.",
            "parameters": {
                "type": "object",
                "properties": {"customer_email": {"type": "string"}},
                "required": ["customer_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Refund an order. Only after the customer confirmed.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}},
                "required": ["order_id", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Email the customer a summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]
