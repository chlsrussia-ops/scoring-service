"""init"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
revision = "0001_init"
down_revision = None
def upgrade() -> None:
    op.create_table("score_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(255), nullable=False, unique=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("capped", sa.Boolean(), nullable=False),
        sa.Column("used_fallback", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("review_label", sa.String(64), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("diagnostics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_score_records_created_at", "score_records", ["created_at"])
def downgrade() -> None:
    op.drop_table("score_records")
