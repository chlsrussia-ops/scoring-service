"""production hardening models"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_production_hardening"
down_revision = "0001_init"


def upgrade() -> None:
    # ── Idempotency ──
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(512), nullable=False, unique=True),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_idempotency_key", "idempotency_records", ["idempotency_key"], unique=True)
    op.create_index("ix_idempotency_expires", "idempotency_records", ["expires_at"])

    # ── Job Records ──
    op.create_table(
        "job_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("locked_by", sa.String(255), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_status", "job_records", ["status"])
    op.create_index("ix_job_next_attempt", "job_records", ["next_attempt_at"])
    op.create_index("ix_job_type_status", "job_records", ["job_type", "status"])

    # ── Job Attempts ──
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_job_attempt_job_id", "job_attempts", ["job_id"])

    # ── Outbox Events ──
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dispatch_error", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_created", "outbox_events", ["created_at"])

    # ── Delivery Attempts ──
    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("outbox_event_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(64), nullable=False, server_default="webhook"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_delivery_outbox_id", "delivery_attempts", ["outbox_event_id"])

    # ── Dead Letter Items ──
    op.create_table(
        "dead_letter_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(128), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_history", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="failed"),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dlq_source_type", "dead_letter_items", ["source_type"])
    op.create_index("ix_dlq_created", "dead_letter_items", ["created_at"])

    # ── Failure Records ──
    op.create_table(
        "failure_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(128), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("payload_snapshot", sa.JSON(), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_failure_entity", "failure_records", ["entity_type", "entity_id"])
    op.create_index("ix_failure_created", "failure_records", ["created_at"])

    # ── Source Health States ──
    op.create_table(
        "source_health_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(255), nullable=False, unique=True),
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantined_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantine_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_name", "source_health_states", ["source_name"], unique=True)

    # ── Quarantine Rules ──
    op.create_table(
        "quarantine_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quarantined_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
    )

    # ── Audit Logs ──
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(128), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_created", "audit_logs", ["created_at"])
    op.create_index("ix_audit_target", "audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("quarantine_rules")
    op.drop_table("source_health_states")
    op.drop_table("failure_records")
    op.drop_table("dead_letter_items")
    op.drop_table("delivery_attempts")
    op.drop_table("outbox_events")
    op.drop_table("job_attempts")
    op.drop_table("job_records")
    op.drop_table("idempotency_records")
