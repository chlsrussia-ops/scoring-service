from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Original model ───────────────────────────────────────────────────

class ScoreRecord(Base):
    __tablename__ = "score_records"
    __table_args__ = (
        Index("ix_score_records_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    capped: Mapped[bool] = mapped_column(Boolean, nullable=False)
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_label: Mapped[str] = mapped_column(String(64), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    diagnostics_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


# ── Idempotency ─────────────────────────────────────────────────────

class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        Index("ix_idempotency_key", "idempotency_key", unique=True),
        Index("ix_idempotency_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ── Job Queue ────────────────────────────────────────────────────────

class JobRecord(Base):
    __tablename__ = "job_records"
    __table_args__ = (
        Index("ix_job_status", "status"),
        Index("ix_job_next_attempt", "next_attempt_at"),
        Index("ix_job_type_status", "job_type", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leased_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (Index("ix_job_attempt_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ── Outbox ───────────────────────────────────────────────────────────

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_status", "status"),
        Index("ix_outbox_created", "created_at"),
        Index("ix_outbox_dedup_key", "dedup_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispatch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (Index("ix_delivery_outbox_id", "outbox_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    outbox_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False, default="webhook")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


# ── Dead Letter / Failures ───────────────────────────────────────────

class DeadLetterItem(Base):
    __tablename__ = "dead_letter_items"
    __table_args__ = (
        Index("ix_dlq_source_type", "source_type"),
        Index("ix_dlq_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="failed")
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FailureRecord(Base):
    __tablename__ = "failure_records"
    __table_args__ = (
        Index("ix_failure_entity", "entity_type", "entity_id"),
        Index("ix_failure_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    payload_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


# ── Source Health / Quarantine ───────────────────────────────────────

class SourceHealthState(Base):
    __tablename__ = "source_health_states"
    __table_args__ = (Index("ix_source_name", "source_name", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quarantined_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class QuarantineRule(Base):
    __tablename__ = "quarantine_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    quarantined_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ── Audit Log ────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_action", "action"),
        Index("ix_audit_created", "created_at"),
        Index("ix_audit_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


# ══════════════════════════════════════════════════════════════════════
# Stage 3: Platform models — tenancy, policies, pipeline,
#           explanations, usage, exports, widgets
# ══════════════════════════════════════════════════════════════════════

import enum

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship


# ── Tenancy ──────────────────────────────────────────────────────────

class TenantStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    archived = "archived"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[TenantStatus] = mapped_column(
        String(16),
        nullable=False, default=TenantStatus.active,
    )
    plan: Mapped[str] = mapped_column(String(64), nullable=False, default="free")
    settings_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    workspaces: Mapped[list["Workspace"]] = relationship("Workspace", back_populates="tenant", lazy="selectin")
    api_clients: Mapped[list["ApiClient"]] = relationship("ApiClient", back_populates="tenant", lazy="selectin")


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_workspace_tenant_slug"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    settings_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="workspaces")


class ApiClient(Base):
    __tablename__ = "api_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_clients")


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_email", name="uq_membership_tenant_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
    )
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Policies ─────────────────────────────────────────────────────────

class PolicyType(str, enum.Enum):
    detection = "detection"
    scoring = "scoring"
    recommendation = "recommendation"
    alert = "alert"
    suppression = "suppression"


class PolicyStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    inactive = "inactive"
    archived = "archived"


class PolicyBundle(Base):
    __tablename__ = "policy_bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_type: Mapped[PolicyType] = mapped_column(
        String(32), nullable=False,
    )
    status: Mapped[PolicyStatus] = mapped_column(
        String(16),
        nullable=False, default=PolicyStatus.draft,
    )
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    versions: Mapped[list["PolicyVersion"]] = relationship("PolicyVersion", back_populates="bundle", lazy="selectin")


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("bundle_id", "version", name="uq_policy_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policy_bundles.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    bundle: Mapped["PolicyBundle"] = relationship("PolicyBundle", back_populates="versions")


class DetectionRule(Base):
    __tablename__ = "detection_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    conditions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, default="flag")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ScoringProfile(Base):
    __tablename__ = "scoring_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weights_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    min_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)


class AlertPolicy(Base):
    __tablename__ = "alert_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    conditions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SuppressionPolicy(Base):
    __tablename__ = "suppression_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    suppress_action: Mapped[str] = mapped_column(String(64), nullable=False, default="drop")
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ── Pipeline / Processing ───────────────────────────────────────────

class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True,
    )
    run_type: Mapped[str] = mapped_column(String(64), nullable=False, default="scheduled")
    status: Mapped[RunStatus] = mapped_column(
        String(16),
        nullable=False, default=RunStatus.pending,
    )
    source_filter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stats_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ProcessingStage(Base):
    __tablename__ = "processing_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    stage_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        String(16),
        nullable=False, default=RunStatus.pending,
    )
    items_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProcessingCheckpoint(Base):
    __tablename__ = "processing_checkpoints"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "checkpoint_key", name="uq_checkpoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    checkpoint_key: Mapped[str] = mapped_column(String(255), nullable=False)
    checkpoint_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class BackfillRequest(Base):
    __tablename__ = "backfill_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processing_runs.id", ondelete="SET NULL"), nullable=True,
    )
    source_filter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        String(16),
        nullable=False, default=RunStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RebuildRequest(Base):
    __tablename__ = "rebuild_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processing_runs.id", ondelete="SET NULL"), nullable=True,
    )
    target: Mapped[str] = mapped_column(String(64), nullable=False, default="all")
    status: Mapped[RunStatus] = mapped_column(
        String(16),
        nullable=False, default=RunStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class PipelineEvent(Base):
    __tablename__ = "pipeline_events"
    __table_args__ = (
        Index("ix_pipeline_events_tenant_source", "tenant_id", "source"),
        Index("ix_pipeline_events_ingested", "tenant_id", "ingested_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_tenant_category", "tenant_id", "category"),
        Index("ix_signals_tenant_topic", "tenant_id", "topic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Trend(Base):
    __tablename__ = "trends"
    __table_args__ = (
        Index("ix_trends_tenant_score", "tenant_id", "score"),
        Index("ix_trends_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    direction: Mapped[str] = mapped_column(String(32), nullable=False, default="rising")
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    growth_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recs_tenant_priority", "tenant_id", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trend_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("trends.id", ondelete="SET NULL"), nullable=True,
    )
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trend_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("trends.id", ondelete="SET NULL"), nullable=True,
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ── Explainability ───────────────────────────────────────────────────

class DecisionTrace(Base):
    __tablename__ = "decision_traces"
    __table_args__ = (
        Index("ix_decision_trace_entity", "tenant_id", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    matched_rules_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    factor_contributions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class SignalLineageLink(Base):
    __tablename__ = "signal_lineage_links"
    __table_args__ = (
        Index("ix_lineage_from", "tenant_id", "from_type", "from_id"),
        Index("ix_lineage_to", "tenant_id", "to_type", "to_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_type: Mapped[str] = mapped_column(String(64), nullable=False)
    to_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, default="derived_from")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class TrendEvidence(Base):
    __tablename__ = "trend_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trend_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trends.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Usage / Quotas ───────────────────────────────────────────────────

class PlanDefinition(Base):
    __tablename__ = "plan_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    limits_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    features_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("tenant_id", "metric", "period", name="uq_usage_counter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
    )
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    period: Mapped[str] = mapped_column(String(32), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class QuotaEnforcementLog(Base):
    __tablename__ = "quota_enforcement_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Exports / Widgets ────────────────────────────────────────────────

class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    export_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="json")
    filters_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[RunStatus] = mapped_column(
        String(16),
        nullable=False, default=RunStatus.pending,
    )
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WidgetConfig(Base):
    __tablename__ = "widget_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    widget_type: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Stage 4: Data Sources ──────────────────────────────────────────

class SourceType(str, enum.Enum):
    rss = "rss"
    reddit = "reddit"
    http_api = "http_api"
    file_import = "file_import"
    twitter = "twitter"


class SourceStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    error = "error"
    syncing = "syncing"


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_normalized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_data_sources_tenant_type", "tenant_id", "source_type"),
    )


# ── Stage 4: LLM Layer ─────────────────────────────────────────────

class LlmGeneration(Base):
    __tablename__ = "llm_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_template: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("ix_llm_gen_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_llm_gen_dedup", "tenant_id", "entity_type", "entity_id", "prompt_template", "input_hash"),
    )


class DigestReport(Base):
    __tablename__ = "digest_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_trends_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    top_recommendations_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    key_risks_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    stats_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    llm_generation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class DemoRun(Base):
    __tablename__ = "demo_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ══════════════════════════════════════════════════════════════════════
# Stage 5: Adaptation & Self-Improving System
# ══════════════════════════════════════════════════════════════════════


# ── Feedback & Outcomes ──────────────────────────────────────────────

class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (
        Index("ix_feedback_target", "target_type", "target_id"),
        Index("ix_feedback_tenant", "tenant_id"),
        Index("ix_feedback_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)  # trend/recommendation/alert/source/action/run
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(64), nullable=False)  # relevance/usefulness/accuracy/quality
    label: Mapped[str] = mapped_column(String(64), nullable=False)  # relevant/noise/useful/useless/false_positive/true_positive/late/early
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    usefulness_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    confidence_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="human")  # human/system/inferred
    evidence_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class OutcomeRecord(Base):
    __tablename__ = "outcome_records"
    __table_args__ = (
        Index("ix_outcome_entity", "entity_type", "entity_id"),
        Index("ix_outcome_tenant", "tenant_id"),
        Index("ix_outcome_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # trend/recommendation/alert/source
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome_type: Mapped[str] = mapped_column(String(64), nullable=False)  # confirmed/rejected/expired/acted_on/ignored
    outcome_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    measurement_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Evaluation & Quality Metrics ─────────────────────────────────────

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index("ix_eval_run_tenant", "tenant_id"),
        Index("ix_eval_run_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # None = global
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_label: Mapped[str] = mapped_column(String(32), nullable=False, default="24h")  # 24h/7d/30d
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    comparison_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # vs previous window
    degradation_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    improvement_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sample_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index("ix_metric_snap_eval", "evaluation_run_id"),
        Index("ix_metric_snap_name", "metric_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    segment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # source/category/policy/tenant
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_improved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Adaptive Scoring ─────────────────────────────────────────────────

class AdaptiveScoringProfile(Base):
    __tablename__ = "adaptive_scoring_profiles"
    __table_args__ = (
        Index("ix_asp_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_asp_tenant_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weights_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # factor -> weight adjustment
    source_trust_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # source -> multiplier
    category_trust_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # category -> multiplier
    thresholds_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # threshold overrides
    calibration_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # calibration rules
    safe_bounds_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # min/max per parameter
    parent_profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class AdaptiveScoringLog(Base):
    __tablename__ = "adaptive_scoring_logs"
    __table_args__ = (
        Index("ix_asl_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_score: Mapped[float] = mapped_column(Float, nullable=False)
    adjusted_score: Mapped[float] = mapped_column(Float, nullable=False)
    adjustments_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # factor -> delta
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Policy Auto-Tuning ───────────────────────────────────────────────

class AdaptationProposal(Base):
    __tablename__ = "adaptation_proposals"
    __table_args__ = (
        Index("ix_proposal_tenant", "tenant_id"),
        Index("ix_proposal_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposal_type: Mapped[str] = mapped_column(String(64), nullable=False)  # threshold/weight/suppression/source_trust/priority
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)  # policy/scoring_profile/source/category
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    current_value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposed_value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    delta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="safe")  # safe/moderate/risky
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending/approved/rejected/applied/rolled_back/expired
    evaluation_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experiment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    simulation_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AdaptationVersion(Base):
    __tablename__ = "adaptation_versions"
    __table_args__ = (
        Index("ix_adapt_ver_profile", "profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RollbackRecord(Base):
    __tablename__ = "rollback_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    from_version: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rolled_back_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    metrics_before_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics_after_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Goal-Driven Optimization ─────────────────────────────────────────

class GoalDefinition(Base):
    __tablename__ = "goal_definitions"
    __table_args__ = (
        Index("ix_goal_tenant", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_metric: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="maximize")  # maximize/minimize
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    guardrails_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # {metric: {min: x, max: y}}
    segment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # tenant/source/category
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evaluation_window: Mapped[str] = mapped_column(String(32), nullable=False, default="7d")
    adaptation_strategy: Mapped[str] = mapped_column(String(64), nullable=False, default="conservative")  # conservative/moderate/aggressive
    approval_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="suggest_only")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_proposals: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    trade_offs_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    guardrail_violations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendations_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Experimentation / Shadow / Replay ─────────────────────────────────

class AdaptationExperiment(Base):
    __tablename__ = "adaptation_experiments"
    __table_args__ = (
        Index("ix_experiment_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    experiment_type: Mapped[str] = mapped_column(String(64), nullable=False)  # shadow/replay/canary
    proposal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    candidate_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending/running/completed/failed
    baseline_metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    candidate_metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    comparison_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)  # better/worse/neutral/inconclusive
    verdict_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    degradation_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ── Source Learning / Trust Evolution ─────────────────────────────────

class SourceTrustHistory(Base):
    __tablename__ = "source_trust_history"
    __table_args__ = (
        Index("ix_sth_source", "source_name"),
        Index("ix_sth_tenant", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    noise_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timeliness_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confirmation_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)  # per-topic trust
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class SourceTrustCurrent(Base):
    __tablename__ = "source_trust_current"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_name", "topic_key", name="uq_source_trust"),
        Index("ix_stc_tenant_source", "tenant_id", "source_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_key: Mapped[str] = mapped_column(String(255), nullable=False, default="__global__")
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    noise_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timeliness_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confirmation_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    volatility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


# ── Self-Evaluation & Quality ─────────────────────────────────────────

class SelfEvaluationReport(Base):
    __tablename__ = "self_evaluation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)  # quality/adaptation/drift/issue
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics_before_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics_after_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ══════════════════════════════════════════════════════════════════════
# Stage 6: Ranking Evaluation Framework
# ══════════════════════════════════════════════════════════════════════


class BenchmarkDataset(Base):
    __tablename__ = "benchmark_datasets"
    __table_args__ = (
        Index("ix_benchmark_ds_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", "version", name="uq_benchmark_ds_name_ver"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    benchmark_type: Mapped[str] = mapped_column(String(64), nullable=False, default="ranking")  # ranking/classification/scoring
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class BenchmarkItem(Base):
    __tablename__ = "benchmark_items"
    __table_args__ = (
        Index("ix_bench_item_dataset", "dataset_id"),
        Index("ix_bench_item_segment", "segment_category", "segment_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("benchmark_datasets.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # the item to rank/score
    expected_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_label: Mapped[str | None] = mapped_column(String(64), nullable=True)  # relevant/irrelevant/high/low
    relevance_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-4 graded relevance for nDCG
    segment_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)  # easy/medium/hard
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalRunRecord(Base):
    __tablename__ = "eval_run_records"
    __table_args__ = (
        Index("ix_eval_rec_tenant", "tenant_id"),
        Index("ix_eval_rec_dataset", "dataset_id"),
        Index("ix_eval_rec_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("benchmark_datasets.id", ondelete="CASCADE"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending/running/completed/failed
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalItemResult(Base):
    __tablename__ = "eval_item_results"
    __table_args__ = (
        Index("ix_eval_item_run", "run_id"),
        Index("ix_eval_item_benchmark", "benchmark_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    benchmark_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("benchmark_items.id", ondelete="CASCADE"), nullable=False)
    predicted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # True if item appeared in top-k
    rank_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)  # predicted_rank - expected_rank
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalMetricResult(Base):
    __tablename__ = "eval_metric_results"
    __table_args__ = (
        Index("ix_eval_metric_run", "run_id"),
        Index("ix_eval_metric_name", "metric_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    k: Mapped[int | None] = mapped_column(Integer, nullable=True)  # for @k metrics
    segment_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalComparison(Base):
    __tablename__ = "eval_comparisons"
    __table_args__ = (
        Index("ix_eval_comp_baseline", "baseline_run_id"),
        Index("ix_eval_comp_candidate", "candidate_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baseline_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    candidate_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # better/worse/neutral/regression/pending
    verdict_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_diffs_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    segment_diffs_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    regression_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    improvement_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    guardrail_violations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RegressionGuardrail(Base):
    __tablename__ = "regression_guardrails"
    __table_args__ = (
        Index("ix_guardrail_tenant", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_regression_delta: Mapped[float | None] = mapped_column(Float, nullable=True)  # max allowed drop
    segment_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="error")  # error/warning
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ══════════════════════════════════════════════════════════════════════
# Stage 7: Workflow Orchestration
# ══════════════════════════════════════════════════════════════════════


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_wf_run_tenant", "tenant_id"),
        Index("ix_wf_run_status", "status"),
        Index("ix_wf_run_type", "workflow_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending/running/completed/failed/cancelled
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_step: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(128), nullable=False, default="api")  # api/schedule/manual/system
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        Index("ix_wf_step_run", "workflow_run_id"),
        Index("ix_wf_step_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending/running/completed/failed/skipped
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index("ix_sched_job_next", "next_run_at"),
        Index("ix_sched_job_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    workflow_type: Mapped[str] = mapped_column(String(128), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(128), nullable=True)  # e.g. "0 */6 * * *"
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)  # alternative to cron
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
