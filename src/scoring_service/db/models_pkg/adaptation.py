"""Auto-split from monolithic models.py."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, Index, Integer, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from scoring_service.db.models_pkg._base import Base, _utcnow

import enum
from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship


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


