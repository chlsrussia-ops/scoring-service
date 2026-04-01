"""Domain event and data contracts — versioned schemas for all inter-module data."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from scoring_service.contracts_registry.registry import Compatibility, contract_registry


# ══════════════════════════════════════════════════════════════════════
# Scoring Domain
# ══════════════════════════════════════════════════════════════════════

class ScoreCompletedEventV1(BaseModel):
    """Event emitted when scoring completes."""
    model_config = ConfigDict(extra="forbid")
    request_id: str
    source: str
    score: float
    review_label: str
    approved: bool
    capped: bool = False
    correlation_id: str | None = None
    timestamp: str | None = None


class ScoreCompletedEventV2(BaseModel):
    """V2: adds tenant_id and breakdown."""
    model_config = ConfigDict(extra="forbid")
    request_id: str
    source: str
    score: float
    review_label: str
    approved: bool
    capped: bool = False
    tenant_id: str | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    timestamp: str | None = None


# ══════════════════════════════════════════════════════════════════════
# Adaptation Domain
# ══════════════════════════════════════════════════════════════════════

class FeedbackEventContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: str
    target_id: int
    feedback_type: str
    label: str
    score: float | None = None
    reviewer: str = "human"
    source: str = "human"


class AdaptationProposalContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_type: str
    target_type: str
    target_id: str
    current_value: dict[str, Any]
    proposed_value: dict[str, Any]
    delta: dict[str, Any]
    reason: str
    risk_level: str


class EvaluationResultContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_run_id: int
    tenant_id: str | None = None
    window_label: str
    metrics: dict[str, float]
    degradation_flags: list[str] = Field(default_factory=list)
    improvement_flags: list[str] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# Evaluation Domain
# ══════════════════════════════════════════════════════════════════════

class BenchmarkResultContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: int
    dataset_id: int
    strategy_name: str
    strategy_version: str
    status: str
    item_count: int
    metrics: dict[str, float]
    duration_ms: int | None = None


class ComparisonVerdictContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_id: int
    baseline_run_id: int
    candidate_run_id: int
    verdict: str
    verdict_reason: str
    regression_flags: list[str] = Field(default_factory=list)
    guardrail_violations: list[str] = Field(default_factory=list)
    ci_pass: bool


# ══════════════════════════════════════════════════════════════════════
# Workflow Domain
# ══════════════════════════════════════════════════════════════════════

class WorkflowCompletedContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_run_id: int
    workflow_type: str
    status: str
    completed_steps: int
    total_steps: int
    triggered_by: str
    correlation_id: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)


class WorkflowStepResultContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_run_id: int
    step_name: str
    status: str
    attempts: int
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# ══════════════════════════════════════════════════════════════════════
# Pipeline Domain
# ══════════════════════════════════════════════════════════════════════

class TrendDetectedContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trend_id: int
    tenant_id: str
    source: str
    category: str
    topic: str
    score: float
    confidence: float
    direction: str
    event_count: int


class RecommendationCreatedContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_id: int
    tenant_id: str
    trend_id: int | None = None
    category: str
    title: str
    priority: str
    confidence: float


class AlertFiredContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: int
    tenant_id: str
    alert_type: str
    severity: str
    title: str
    trend_id: int | None = None


# ══════════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════════

def register_all_contracts() -> int:
    """Register all domain contracts. Returns count."""
    registrations = [
        # Scoring
        ("score.completed", 1, ScoreCompletedEventV1, "scoring", "Score completion event v1"),
        ("score.completed", 2, ScoreCompletedEventV2, "scoring", "Score completion event v2 — adds tenant_id, breakdown"),
        # Adaptation
        ("feedback.created", 1, FeedbackEventContractV1, "adaptation", "Feedback event"),
        ("adaptation.proposal", 1, AdaptationProposalContractV1, "adaptation", "Adaptation proposal"),
        ("evaluation.result", 1, EvaluationResultContractV1, "adaptation", "Evaluation result"),
        # Evaluation
        ("benchmark.result", 1, BenchmarkResultContractV1, "evaluation", "Benchmark run result"),
        ("comparison.verdict", 1, ComparisonVerdictContractV1, "evaluation", "Comparison verdict"),
        # Workflow
        ("workflow.completed", 1, WorkflowCompletedContractV1, "workflow", "Workflow completion"),
        ("workflow.step_result", 1, WorkflowStepResultContractV1, "workflow", "Workflow step result"),
        # Pipeline
        ("trend.detected", 1, TrendDetectedContractV1, "pipeline", "Trend detected event"),
        ("recommendation.created", 1, RecommendationCreatedContractV1, "pipeline", "Recommendation created"),
        ("alert.fired", 1, AlertFiredContractV1, "pipeline", "Alert fired event"),
    ]

    for name, version, schema, domain, desc in registrations:
        contract_registry.register(name, version, schema, domain, desc)

    # Deprecate v1 of score.completed in favor of v2
    contract_registry.deprecate("score.completed", 1, deprecated_by="score.completed:v2")

    return len(registrations)
