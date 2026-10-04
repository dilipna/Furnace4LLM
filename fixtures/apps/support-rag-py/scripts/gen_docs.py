"""Generate the Kilnworks knowledge base (fictional product) from a fact table.

Each document has a stable id and a set of atomic facts. The same table is used
to build the eval set, so grounding/citation checks have verifiable answers.

    python scripts/gen_docs.py   # writes docs/*.md and docs/facts.json
"""

from __future__ import annotations

import json
from pathlib import Path

DOCS: list[dict] = [
    {
        "id": "plans",
        "title": "Plans and pricing",
        "facts": [
            ("How much does the Studio plan cost?", "The Studio plan costs $29 per month and supports up to 3 kilns."),
            ("How many kilns does the Workshop plan support?", "The Workshop plan costs $79 per month and supports up to 12 kilns."),
            ("Is there a free trial?", "Every plan starts with a 14-day free trial; no card is required."),
        ],
    },
    {
        "id": "billing",
        "title": "Billing and invoices",
        "facts": [
            ("When are invoices issued?", "Invoices are issued on the 1st of each month in UTC."),
            ("Which payment methods are accepted?", "Kilnworks accepts Visa, Mastercard and SEPA direct debit."),
            ("How do I get a refund?", "Refunds are available within 30 days of a charge and are processed by the support team after a ticket is opened."),
        ],
    },
    {
        "id": "pairing",
        "title": "Pairing a kiln controller",
        "facts": [
            ("How do I pair a controller?", "Hold the PAIR button for 5 seconds until the LED blinks blue, then enter the 6-digit code shown in the app."),
            ("What network does the controller need?", "Controllers require 2.4 GHz Wi-Fi; 5 GHz networks are not supported."),
        ],
    },
    {
        "id": "error-codes",
        "title": "Controller error codes",
        "facts": [
            ("What does error E14 mean?", "E14 means the thermocouple is disconnected; reseat the thermocouple connector and restart the firing."),
            ("What does error E22 mean?", "E22 means the kiln exceeded its configured maximum temperature and the firing was stopped automatically."),
            ("What does error E31 mean?", "E31 means the controller lost Wi-Fi for more than 10 minutes; the firing continues locally."),
        ],
    },
    {
        "id": "firing-schedules",
        "title": "Firing schedules",
        "facts": [
            ("How many segments can a schedule have?", "A firing schedule can have up to 16 segments."),
            ("Can I edit a schedule during a firing?", "Schedules cannot be edited while a firing is running; you can only skip to the next segment."),
        ],
    },
    {
        "id": "alerts",
        "title": "Alerts and notifications",
        "facts": [
            ("Which alert channels exist?", "Alerts can be sent by push notification, email and SMS; SMS is available on the Workshop plan only."),
            ("How fast are temperature alerts?", "Temperature alerts are delivered within 60 seconds of the threshold being crossed."),
        ],
    },
    {
        "id": "data-retention",
        "title": "Data retention",
        "facts": [
            ("How long is firing history kept?", "Firing history is kept for 24 months on all plans."),
            ("Can I export my data?", "You can export all firing logs as CSV from Settings > Data."),
        ],
    },
    {
        "id": "team-access",
        "title": "Team access and roles",
        "facts": [
            ("What roles exist?", "Kilnworks has three roles: Owner, Technician and Viewer."),
            ("Can a Viewer start a firing?", "Viewers cannot start or stop firings; only Owners and Technicians can."),
        ],
    },
    {
        "id": "api",
        "title": "Public API",
        "facts": [
            ("What is the API rate limit?", "The public API allows 600 requests per minute per organization."),
            ("How do I authenticate to the API?", "API requests use a bearer token created in Settings > API keys."),
        ],
    },
    {
        "id": "safety",
        "title": "Safety interlocks",
        "facts": [
            ("What happens if the lid opens?", "If the lid sensor detects an open lid, heating elements are cut within 2 seconds."),
            ("Can safety interlocks be disabled remotely?", "Safety interlocks cannot be disabled remotely under any plan."),
        ],
    },
    {
        "id": "firmware",
        "title": "Firmware updates",
        "facts": [
            ("How are firmware updates installed?", "Firmware updates install automatically between firings and never during an active firing."),
            ("What is the current firmware version?", "The current controller firmware is version 4.2.1."),
        ],
    },
    {
        "id": "warranty",
        "title": "Hardware warranty",
        "facts": [
            ("How long is the controller warranty?", "Kiln controllers have a 2-year limited hardware warranty."),
            ("Are thermocouples covered by warranty?", "Thermocouples are consumables and are not covered by the warranty."),
        ],
    },
    {
        "id": "support-hours",
        "title": "Support hours",
        "facts": [
            ("When is support available?", "Human support is available Monday to Friday, 08:00 to 18:00 CET."),
            ("How fast does support respond?", "Support responds to tickets within 1 business day; Workshop plan tickets within 4 business hours."),
        ],
    },
    {
        "id": "account-deletion",
        "title": "Deleting an account",
        "facts": [
            ("How do I delete my account?", "Account deletion is requested from Settings > Account and completes within 7 days."),
            ("Is deleted data recoverable?", "Deleted accounts and firing history cannot be recovered."),
        ],
    },
    {
        "id": "offline-mode",
        "title": "Offline mode",
        "facts": [
            ("Does the controller work offline?", "Controllers run stored schedules offline and sync logs when the connection returns."),
        ],
    },
    {
        "id": "integrations",
        "title": "Integrations",
        "facts": [
            ("Which integrations are supported?", "Kilnworks integrates with Slack and with generic webhooks."),
            ("Do webhooks retry?", "Failed webhook deliveries are retried 5 times with exponential backoff."),
        ],
    },
]


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "docs"
    root.mkdir(exist_ok=True)
    facts = []
    for doc in DOCS:
        body = [f"# {doc['title']}", ""]
        for q, a in doc["facts"]:
            body += [f"## {q}", "", a, ""]
            facts.append({"doc_id": doc["id"], "question": q, "answer": a})
        (root / f"{doc['id']}.md").write_text("\n".join(body), encoding="utf-8")
    (root / "facts.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    print(f"wrote {len(DOCS)} docs, {len(facts)} facts")


if __name__ == "__main__":
    main()
