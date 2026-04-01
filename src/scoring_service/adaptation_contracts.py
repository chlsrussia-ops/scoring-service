"""Pydantic schemas for Stage 5: Adaptation & Self-Improving System."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Feedback ─────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: str = Field(pattern=r"^(trend|recommendation|alert|source|action|run)$")
    target_id: int
    feedback_type: str = Field(pattern=r"^(relevance|usefulness|accuracy|quality|timeliness)$")
    label: str = Field(min_length=1, max_length=64)
    score: float | None = None
    usefulness_rating: int | None = Field(default=None, ge=1, le=5)
    confidence_rating: float | None = Field(default=None, ge=0.0, le=1.0)
    reviewer: str = "human"
    source: str = Field(default="human", pattern=r"^(human|system|inferred)$")
    evidence_snapshot: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    target_type: str
    target_id: int
    feedback_type: str
    label: str
    score: float | None
    usefulness_rating: int | None
    reviewer: str
    source: str
    created_at: datetime


# ── Outcomes ─────────────────────────────────────────────────────────

class OutcomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: str = Field(pattern=r"^(trend|recommendation|alert|source)$")
    entity_id: int
    outcome_type: str = Field(pattern=r"^(confirmed|rejected|expired|acted_on|ignored|false_positive|true_positive)$")
    outcome_value: str | None = None
    measurement_window_hours: int = Field(default=24, ge=1, le=720)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)


class OutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    entity_type: str
    entity_id: int
    outcome_type: str
    outcome_value: str | None
    confidence: float
    measured_at: datetime
    created_at: datetime


# ── Evaluation ───────────────────────────────────────────────────────

class EvaluationSummary(BaseModel):
    evaluation_run_id: int
    tenant_id: str | None
    window_label: str
    status: str
    metrics: dict[str, float]
    comparison: dict[str, Any] | None = None
    degradation_flags: list[str] = Field(default_factory=list)
    improvement_flags: list[str] = Field(default_factory=list)
    sample_counts: dict[str, int] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None


class ScorecardOut(BaseModel):
    tenant_id: str | None
    window: str
    alert_precision: float | None = None
    alert_acceptance_rate: float | None = None
    recommendation_usefulness: float | None = None
    trend_confirmation_rate: float | None = None
    noise_rate: float | None = None
    false_positive_rate: float | None = None
    source_quality_avg: float | None = None
    suppression_effectiveness: float | None = None
    sample_counts: dict[str, int] = Field(default_factory=dict)


# ── Adaptive Scoring ─────────────────────────────────────────────────

class AdaptiveScoringProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str | None
    name: str
    is_active: bool
    version: int
    weights_json: dict[str, Any]
    source_trust_json: dict[str, Any]
    category_trust_json: dict[str, Any]
    thresholds_json: dict[str, Any]
    created_at: datetime


class ScoringAdjustmentOut(BaseModel):
    entity_type: str
    entity_id: int
    base_score: float
    adjusted_score: float
    adjustments: dict[str, float]
    explanation: str


# ── Proposals ────────────────────────────────────────────────────────

class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str | None
    proposal_type: str
    target_type: str
    target_id: str
    current_value_json: dict[str, Any]
    proposed_value_json: dict[str, Any]
    delta_json: dict[str, Any]
    reason: str
    risk_level: str
    status: str
    evaluation_run_id: int | None
    experiment_id: int | None
    simulation_result_json: dict[str, Any] | None
    approved_by: str | None
    approved_at: datetime | None
    applied_at: datetime | None
    rolled_back_at: datetime | None
    created_at: datetime


class ProposalAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = "admin"


# ── Goals ────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    target_metric: str = Field(min_length=1, max_length=128)
    direction: str = Field(default="maximize", pattern=r"^(maximize|minimize)$")
    target_value: float | None = None
    guardrails: dict[str, Any] = Field(default_factory=dict)
    segment_type: str | None = None
    segment_value: str | None = None
    evaluation_window: str = "7d"
    adaptation_strategy: str = Field(default="conservative", pattern=r"^(conservative|moderate|aggressive)$")
    approval_mode: str = Field(default="suggest_only", pattern=r"^(suggest_only|auto_safe|approval_required)$")
    priority: int = 100


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str | None
    name: str
    description: str | None
    target_metric: str
    direction: str
    target_value: float | None
    guardrails_json: dict[str, Any]
    segment_type: str | None
    segment_value: str | None
    evaluation_window: str
    adaptation_strategy: str
    approval_mode: str
    is_active: bool
    priority: int
    created_at: datetime


class GoalPerformanceOut(BaseModel):
    goal_id: int
    goal_name: str
    target_metric: str
    direction: str
    current_value: float | None
    target_value: float | None
    progress_pct: float | None
    status: str  # on_track / at_risk / off_track / achieved
    guardrail_violations: list[str] = Field(default_factory=list)


# ── Experiments ──────────────────────────────────────────────────────

class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str | None
    name: str
    experiment_type: str
    proposal_id: int | None
    status: str
    baseline_metrics_json: dict[str, Any]
    candidate_metrics_json: dict[str, Any]
    comparison_json: dict[str, Any] | None
    verdict: str | None
    verdict_reason: str | None
    items_evaluated: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


# ── Source Learning ──────────────────────────────────────────────────

class SourceTrustOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str | None
    source_name: str
    topic_key: str
    trust_score: float
    reliability_score: float
    noise_score: float
    timeliness_score: float
    confirmation_rate: float
    volatility_score: float
    sample_count: int
    last_updated: datetime


class SourceLearningSummary(BaseModel):
    tenant_id: str | None
    sources: list[SourceTrustOut]
    noisy_sources: list[str] = Field(default_factory=list)
    boosted_sources: list[str] = Field(default_factory=list)
    degraded_sources: list[str] = Field(default_factory=list)


# ── Adaptation Status ────────────────────────────────────────────────

class AdaptationStatusOut(BaseModel):
    mode: str
    enabled: bool
    pending_proposals: int
    active_experiments: int
    active_goals: int
    recent_evaluations: int
    recent_rollbacks: int
    last_evaluation_at: datetime | None
    degraded_metrics: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


# ── Self-Evaluation ──────────────────────────────────────────────────

class SelfEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str | None
    report_type: str
    entity_type: str | None
    entity_id: int | None
    summary: str
    quality_score: float | None
    explanation: str | None
    created_at: datetime
