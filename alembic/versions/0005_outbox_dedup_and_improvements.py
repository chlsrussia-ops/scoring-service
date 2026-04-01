"""outbox dedup key and improvements"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0005_outbox_dedup"
down_revision = "0004_stage4_product"

def upgrade() -> None:
    # Add dedup_key to outbox for idempotent dispatch
    op.add_column("outbox_events", sa.Column("dedup_key", sa.String(255), nullable=True))
    op.create_index("ix_outbox_dedup_key", "outbox_events", ["dedup_key"])

    # Add worker_heartbeat column to track last worker activity
    # (lightweight — no new table needed)

def downgrade() -> None:
    op.drop_index("ix_outbox_dedup_key")
    op.drop_column("outbox_events", "dedup_key")
