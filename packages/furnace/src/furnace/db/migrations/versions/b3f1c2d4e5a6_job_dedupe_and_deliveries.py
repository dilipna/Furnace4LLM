"""job dedupe keys, per-job timeouts, webhook delivery audit columns

Revision ID: b3f1c2d4e5a6
Revises: 8db14bfa0ba6
Create Date: 2026-10-11 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f1c2d4e5a6"
down_revision: str | None = "8db14bfa0ba6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("dedupe_key", sa.String(length=300), nullable=True))
    op.add_column("jobs", sa.Column("timeout_s", sa.Integer(), nullable=True))
    op.create_index(
        "uq_jobs_active_dedupe",
        "jobs",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL AND status IN ('queued', 'running')"),
    )
    op.add_column("webhook_deliveries", sa.Column("action", sa.String(length=50), nullable=True))
    op.add_column("webhook_deliveries", sa.Column("repo", sa.String(length=300), nullable=True))
    op.add_column(
        "webhook_deliveries", sa.Column("installation_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column("source", sa.String(length=20), server_default="push", nullable=False),
    )
    op.add_column("webhook_deliveries", sa.Column("outcome", sa.String(length=40), nullable=True))
    op.add_column("webhook_deliveries", sa.Column("detail", sa.Text(), nullable=True))
    op.add_column("webhook_deliveries", sa.Column("job_id", sa.UUID(), nullable=True))
    op.create_index("ix_webhook_deliveries_repo", "webhook_deliveries", ["repo"])


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_repo", table_name="webhook_deliveries")
    for col in ("job_id", "detail", "outcome", "source", "installation_id", "repo", "action"):
        op.drop_column("webhook_deliveries", col)
    op.drop_index("uq_jobs_active_dedupe", table_name="jobs")
    op.drop_column("jobs", "timeout_s")
    op.drop_column("jobs", "dedupe_key")
