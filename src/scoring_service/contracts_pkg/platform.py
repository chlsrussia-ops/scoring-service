"""Pydantic schemas for Stage 3 platform API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Tenancy ────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128)
    plan: str = Field(default="free", max_length=64)
    settings: dict[str, Any] = Field(default_factory=dict)


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    status: str
    plan: str
    settings_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    plan: str | None = None
    status: str | None = None
    settings: dict[str, Any] | None = None


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128)
    settings: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    name: str
    slug: str
    settings_json: dict[str, Any]
    is_default: bool
    created_at: datetime


class ApiClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(min_length=8, max_length=255)
    name: str = Field(default="default", max_length=255)
    scopes: list[str] = Field(default_factory=list)


class ApiClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    api_key: str
    name: str
    is_active: bool
    scopes: list[str]
    created_at: datetime


# ── Policies ───────────────────────────────────────────────────────

class PolicyCondition(BaseModel):
    """Declarative condition for rule evaluation."""
    model_config = ConfigDict(extra="forbid")
    field: str
    operator: str = Field(pattern=r"^(eq|neq|gt|gte|lt|lte|in|contains|between|exists|not_exists)$")
    value: Any


class PolicyRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    conditions: list[PolicyCondition]
    action: str = "flag"
    weight: float = 1.0
    enabled: bool = True


class PolicyVersionConfig(BaseModel):
    """Full config stored as JSON in policy_versions.config_json."""
    model_config = ConfigDict(extra="forbid")
    rules: list[PolicyRuleConfig] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class PolicyBundleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    policy_type: str = Field(pattern=r"^(detection|scoring|recommendation|alert|suppression)$")
    description: str | None = None
    is_global: bool = False
    priority: int = 100
    config: PolicyVersionConfig


class PolicyBundleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str | None
    workspace_id: str | None
    name: str
    policy_type: str
    status: str
    is_global: bool
    priority: int
    description: str | None
    created_at: datetime
    updated_at: datetime
    active_version: PolicyVersionOut | None = None


class PolicyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bundle_id: int
    version: int
    config_json: dict[str, Any]
    is_active: bool
    created_at: datetime
    activated_at: datetime | None


class PolicyActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dry_run: bool = False


class PolicyEvalResult(BaseModel):
    matched_rules: list[dict[str, Any]]
    actions: list[str]
    weights: dict[str, float]
    dry_run: bool = False


# ── Pipeline ───────────────────────────────────────────────────────

class EventIngest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=64)
    external_id: str | None = None
    payload: dict[str, Any]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    source: str
    event_type: str
    external_id: str | None
    payload_json: dict[str, Any]
    normalized_json: dict[str, Any] | None
    ingested_at: datetime


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    source: str
    category: str
    topic: str
    value: float
    metadata_json: dict[str, Any]
    detected_at: datetime


class TrendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    source: str
    category: str
    topic: str
    score: float
    confidence: float
    direction: str
    event_count: int
    growth_rate: float
    first_seen: datetime
    last_seen: datetime
    metadata_json: dict[str, Any]


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    trend_id: int | None
    category: str
    title: str
    body: str | None
    priority: str
    confidence: float
    status: str
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    trend_id: int | None
    alert_type: str
    severity: str
    title: str
    body: str | None
    status: str
    acknowledged_at: datetime | None
    created_at: datetime


class ProcessingRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    run_type: str
    status: str
    source_filter: str | None
    stats_json: dict[str, Any]
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ProcessingRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_filter: str | None = None
    workspace_id: str | None = None


class BackfillCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_filter: str | None = None
    window_start: datetime
    window_end: datetime


class RebuildCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str = "all"


# ── Explainability ─────────────────────────────────────────────────

class DecisionTraceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    entity_type: str
    entity_id: int
    policy_version_id: int | None
    input_summary_json: dict[str, Any]
    matched_rules_json: list[Any]
    factor_contributions_json: dict[str, Any]
    explanation_text: str | None
    explanation_json: dict[str, Any]
    created_at: datetime


class LineageLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_type: str
    from_id: int
    to_type: str
    to_id: int
    relationship_type: str


class ExplanationResponse(BaseModel):
    trace: DecisionTraceOut | None = None
    lineage: list[LineageLinkOut] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


# ── Usage / Quotas ─────────────────────────────────────────────────

class UsageSummary(BaseModel):
    tenant_id: str
    period: str
    metrics: dict[str, int]
    plan: str
    limits: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


class QuotaStatus(BaseModel):
    metric: str
    current: int
    limit: int
    usage_pct: float
    status: str  # ok / warning / exceeded


class PlanDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    limits_json: dict[str, Any]
    features_json: list[str]


# ── Exports ────────────────────────────────────────────────────────

class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_type: str = Field(pattern=r"^(trends|signals|recommendations|alerts|events)$")
    format: str = Field(default="json", pattern=r"^(json|csv)$")
    filters: dict[str, Any] = Field(default_factory=dict)


class ExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    export_type: str
    format: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    result_json: dict[str, Any] | None


# ── Widgets ────────────────────────────────────────────────────────

class WidgetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    widget_type: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    workspace_id: str | None = None
    position: int = 0


class WidgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    workspace_id: str | None
    name: str
    widget_type: str
    config_json: dict[str, Any]
    position: int


# ── Generic ────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class AnalyticsSummary(BaseModel):
    tenant_id: str
    workspace_id: str | None = None
    total_events: int = 0
    total_signals: int = 0
    total_trends: int = 0
    total_recommendations: int = 0
    total_alerts: int = 0
    top_categories: list[dict[str, Any]] = Field(default_factory=list)
    top_sources: list[dict[str, Any]] = Field(default_factory=list)
