"""Platform API routes — tenant-scoped, typed, authorized."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from scoring_service.platform_contracts import (
    AlertOut,
    AnalyticsSummary,
    ApiClientCreate,
    ApiClientOut,
    BackfillCreate,
    DecisionTraceOut,
    ExplanationResponse,
    ExportCreate,
    ExportOut,
    EventIngest,
    EventOut,
    LineageLinkOut,
    PaginatedResponse,
    PlanDefinitionOut,
    PolicyActivateRequest,
    PolicyBundleCreate,
    PolicyBundleOut,
    PolicyVersionOut,
    ProcessingRunOut,
    ProcessingRunRequest,
    RebuildCreate,
    RecommendationOut,
    SignalOut,
    TenantCreate,
    TenantOut,
    TenantUpdate,
    TrendOut,
    UsageSummary,
    WidgetCreate,
    WidgetOut,
    WorkspaceCreate,
    WorkspaceOut,
)
from scoring_service.tenancy.context import TenantContext, get_admin_context, get_tenant_context
from scoring_service.rate_limit import enforce_rate_limit

platform_router = APIRouter(prefix="/v1", tags=["platform"])
platform_admin_router = APIRouter(prefix="/v1/platform/admin", tags=["platform-admin"])


def _get_db(request: Request):
    factory = getattr(request.app.state, "session_factory", None)
    if not factory:
        raise HTTPException(status_code=503, detail="database unavailable")
    db = factory()
    try:
        yield db
    finally:
        db.close()


# ── Tenants ────────────────────────────────────────────────────────

@platform_router.get("/tenants", response_model=list[TenantOut])
def list_tenants(
    request: Request,
    ctx: TenantContext = Depends(get_admin_context),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    svc = TenancyService(db)
    return svc.list_tenants(limit=limit, offset=offset)


@platform_router.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(
    body: TenantCreate,
    request: Request,
    ctx: TenantContext = Depends(get_admin_context),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    svc = TenancyService(db)
    existing = svc.get_tenant(body.id)
    if existing:
        raise HTTPException(400, "tenant already exists")
    return svc.create_tenant(
        id=body.id, name=body.name, slug=body.slug,
        plan=body.plan, settings=body.settings,
    )


@platform_router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: str,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    if not ctx.is_admin and ctx.tenant_id != tenant_id:
        raise HTTPException(403, "access denied")
    svc = TenancyService(db)
    t = svc.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "tenant not found")
    return t


@platform_router.patch("/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(
    tenant_id: str,
    body: TenantUpdate,
    request: Request,
    ctx: TenantContext = Depends(get_admin_context),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    svc = TenancyService(db)
    t = svc.update_tenant(tenant_id, **body.model_dump(exclude_none=True))
    if not t:
        raise HTTPException(404, "tenant not found")
    return t


# ── Workspaces ─────────────────────────────────────────────────────

@platform_router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    svc = TenancyService(db)
    return svc.list_workspaces(ctx.tenant_id)


@platform_router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    svc = TenancyService(db)
    return svc.create_workspace(
        ctx.tenant_id, id=body.id, name=body.name, slug=body.slug,
        settings=body.settings, is_default=body.is_default,
    )


# ── API Clients ────────────────────────────────────────────────────

@platform_router.post("/api-clients", response_model=ApiClientOut, status_code=201)
def create_api_client(
    body: ApiClientCreate,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    svc = TenancyService(db)
    return svc.create_api_client(
        ctx.tenant_id, api_key=body.api_key, name=body.name, scopes=body.scopes,
    )


@platform_router.get("/api-clients", response_model=list[ApiClientOut])
def list_api_clients(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.tenancy.service import TenancyService
    svc = TenancyService(db)
    return svc.list_api_clients(ctx.tenant_id)


# ── Policies ───────────────────────────────────────────────────────

@platform_router.get("/policies", response_model=list[PolicyBundleOut])
def list_policies(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    policy_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
):
    from scoring_service.policies.service import PolicyService
    svc = PolicyService(db)
    bundles = svc.list_bundles(
        tenant_id=ctx.tenant_id, policy_type=policy_type,
        limit=limit, offset=offset,
    )
    result = []
    for b in bundles:
        active_v = None
        for v in (b.versions or []):
            if v.is_active:
                active_v = PolicyVersionOut.model_validate(v)
                break
        out = PolicyBundleOut.model_validate(b)
        out.active_version = active_v
        result.append(out)
    return result


@platform_router.post("/policies", response_model=PolicyBundleOut, status_code=201)
def create_policy(
    body: PolicyBundleCreate,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.policies.service import PolicyService
    svc = PolicyService(db)
    bundle = svc.create_bundle(
        tenant_id=ctx.tenant_id,
        name=body.name,
        policy_type=body.policy_type,
        description=body.description,
        is_global=body.is_global,
        priority=body.priority,
        config=body.config.model_dump(),
    )
    return PolicyBundleOut.model_validate(bundle)


@platform_router.post("/policies/{policy_id}/activate", response_model=PolicyVersionOut)
def activate_policy(
    policy_id: int,
    body: PolicyActivateRequest,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.policies.service import PolicyService
    svc = PolicyService(db)
    bundle = svc.get_bundle(policy_id)
    if not bundle:
        raise HTTPException(404, "policy not found")
    if bundle.tenant_id and bundle.tenant_id != ctx.tenant_id and not ctx.is_admin:
        raise HTTPException(403, "access denied")
    version = svc.activate_version(policy_id)
    if not version:
        raise HTTPException(404, "no version to activate")
    return PolicyVersionOut.model_validate(version)


@platform_router.post("/policies/{policy_id}/deactivate", response_model=PolicyBundleOut)
def deactivate_policy(
    policy_id: int,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.policies.service import PolicyService
    svc = PolicyService(db)
    bundle = svc.deactivate_bundle(policy_id)
    if not bundle:
        raise HTTPException(404, "policy not found")
    return PolicyBundleOut.model_validate(bundle)


# ── Pipeline / Processing ─────────────────────────────────────────

@platform_router.post("/platform/runs", response_model=ProcessingRunOut, status_code=201)
def start_run(
    body: ProcessingRunRequest,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.pipeline.orchestrator import PipelineOrchestrator
    from scoring_service.plugins.registry import plugin_registry
    from scoring_service.usage.service import UsageService

    # Check quota
    usage_svc = UsageService(db)
    quota = usage_svc.check_quota(ctx.tenant_id, "analysis_runs_per_month")
    if not quota["allowed"]:
        raise HTTPException(429, f"quota exceeded: {quota['metric']}")

    orch = PipelineOrchestrator(db, plugin_registry)
    run = orch.run(
        ctx.tenant_id,
        workspace_id=body.workspace_id or ctx.workspace_id,
        source_filter=body.source_filter,
        run_type="manual",
    )

    # Track usage
    usage_svc.increment(ctx.tenant_id, "analysis_runs_per_month")
    return ProcessingRunOut.model_validate(run)


@platform_router.get("/platform/runs", response_model=list[ProcessingRunOut])
def list_runs(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
):
    from scoring_service.pipeline.orchestrator import PipelineOrchestrator
    from scoring_service.plugins.registry import plugin_registry
    orch = PipelineOrchestrator(db, plugin_registry)
    return orch.list_runs(ctx.tenant_id, limit=limit, offset=offset)


@platform_router.get("/platform/runs/{run_id}", response_model=ProcessingRunOut)
def get_run(
    run_id: int,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.pipeline.orchestrator import PipelineOrchestrator
    from scoring_service.plugins.registry import plugin_registry
    orch = PipelineOrchestrator(db, plugin_registry)
    run = orch.get_run(run_id)
    if not run or run.tenant_id != ctx.tenant_id:
        raise HTTPException(404, "run not found")
    return ProcessingRunOut.model_validate(run)


# ── Ingest Events ──────────────────────────────────────────────────

@platform_router.post("/platform/events", response_model=EventOut, status_code=201)
def ingest_event(
    body: EventIngest,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.db.models import PipelineEvent
    from scoring_service.usage.service import UsageService

    usage_svc = UsageService(db)
    quota = usage_svc.check_quota(ctx.tenant_id, "events_per_month")
    if not quota["allowed"]:
        raise HTTPException(429, f"quota exceeded: {quota['metric']}")

    evt = PipelineEvent(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        source=body.source,
        event_type=body.event_type,
        external_id=body.external_id,
        payload_json=body.payload,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)

    usage_svc.increment(ctx.tenant_id, "events_per_month")
    return EventOut.model_validate(evt)


# ── Platform Queries ───────────────────────────────────────────────

@platform_router.get("/platform/trends")
def query_trends(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    category: str | None = Query(None),
    source: str | None = Query(None),
    topic: str | None = Query(None),
    direction: str | None = Query(None),
    min_score: float | None = Query(None),
    sort_by: str = Query("score"),
    sort_dir: str = Query("desc"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
):
    from scoring_service.platform_api.query import PlatformQueryService
    svc = PlatformQueryService(db)
    items, total = svc.query_trends(
        ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        category=category, source=source, topic=topic,
        direction=direction, min_score=min_score,
        sort_by=sort_by, sort_dir=sort_dir,
        limit=limit, offset=offset,
    )
    return {
        "items": [TrendOut.model_validate(i).model_dump() for i in items],
        "total": total, "limit": limit, "offset": offset,
    }


@platform_router.get("/platform/signals")
def query_signals(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    category: str | None = Query(None),
    source: str | None = Query(None),
    topic: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
):
    from scoring_service.platform_api.query import PlatformQueryService
    svc = PlatformQueryService(db)
    items, total = svc.query_signals(
        ctx.tenant_id, workspace_id=ctx.workspace_id,
        category=category, source=source, topic=topic,
        limit=limit, offset=offset,
    )
    return {
        "items": [SignalOut.model_validate(i).model_dump() for i in items],
        "total": total, "limit": limit, "offset": offset,
    }


@platform_router.get("/platform/recommendations")
def query_recommendations(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
):
    from scoring_service.platform_api.query import PlatformQueryService
    svc = PlatformQueryService(db)
    items, total = svc.query_recommendations(
        ctx.tenant_id, workspace_id=ctx.workspace_id,
        category=category, priority=priority, status=status,
        limit=limit, offset=offset,
    )
    return {
        "items": [RecommendationOut.model_validate(i).model_dump() for i in items],
        "total": total, "limit": limit, "offset": offset,
    }


@platform_router.get("/platform/alerts")
def query_alerts(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    alert_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
):
    from scoring_service.platform_api.query import PlatformQueryService
    svc = PlatformQueryService(db)
    items, total = svc.query_alerts(
        ctx.tenant_id, workspace_id=ctx.workspace_id,
        severity=severity, status=status, alert_type=alert_type,
        limit=limit, offset=offset,
    )
    return {
        "items": [AlertOut.model_validate(i).model_dump() for i in items],
        "total": total, "limit": limit, "offset": offset,
    }


# ── Explanations ───────────────────────────────────────────────────

@platform_router.get("/platform/explanations/trends/{trend_id}")
def explain_trend(
    trend_id: int,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.explanations.service import ExplanationService
    svc = ExplanationService(db)
    trace = svc.get_trace(ctx.tenant_id, "trend", trend_id)
    lineage = svc.get_lineage(ctx.tenant_id, "trend", trend_id)
    evidence = svc.get_evidence(trend_id)
    return {
        "trace": DecisionTraceOut.model_validate(trace).model_dump() if trace else None,
        "lineage": [LineageLinkOut.model_validate(l).model_dump() for l in lineage],
        "evidence": [{"id": e.id, "type": e.evidence_type, "summary": e.summary} for e in evidence],
    }


@platform_router.get("/platform/explanations/recommendations/{rec_id}")
def explain_recommendation(
    rec_id: int,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.explanations.service import ExplanationService
    svc = ExplanationService(db)
    trace = svc.get_trace(ctx.tenant_id, "recommendation", rec_id)
    lineage = svc.get_lineage(ctx.tenant_id, "recommendation", rec_id)
    return {
        "trace": DecisionTraceOut.model_validate(trace).model_dump() if trace else None,
        "lineage": [LineageLinkOut.model_validate(l).model_dump() for l in lineage],
    }


# ── Backfill / Rebuild ────────────────────────────────────────────

@platform_router.post("/platform/backfills", status_code=201)
def create_backfill(
    body: BackfillCreate,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.pipeline.orchestrator import PipelineOrchestrator
    from scoring_service.plugins.registry import plugin_registry
    orch = PipelineOrchestrator(db, plugin_registry)
    bf = orch.create_backfill(
        ctx.tenant_id, body.window_start, body.window_end, body.source_filter,
    )
    return {
        "id": bf.id, "tenant_id": bf.tenant_id, "run_id": bf.run_id,
        "status": bf.status.value if hasattr(bf.status, "value") else str(bf.status),
        "window_start": bf.window_start.isoformat(),
        "window_end": bf.window_end.isoformat(),
    }


@platform_router.post("/platform/rebuilds", status_code=201)
def create_rebuild(
    body: RebuildCreate,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.pipeline.orchestrator import PipelineOrchestrator
    from scoring_service.plugins.registry import plugin_registry
    orch = PipelineOrchestrator(db, plugin_registry)
    rb = orch.create_rebuild(ctx.tenant_id, body.target)
    return {
        "id": rb.id, "tenant_id": rb.tenant_id, "run_id": rb.run_id,
        "target": rb.target,
        "status": rb.status.value if hasattr(rb.status, "value") else str(rb.status),
    }


# ── Usage / Quotas ─────────────────────────────────────────────────

@platform_router.get("/platform/usage")
def get_usage(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    period: str | None = Query(None),
    db=Depends(_get_db),
):
    from scoring_service.usage.service import UsageService
    svc = UsageService(db)
    return svc.get_summary(ctx.tenant_id)


# ── Analytics ──────────────────────────────────────────────────────

@platform_router.get("/platform/analytics")
def get_analytics(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.platform_api.query import PlatformQueryService
    svc = PlatformQueryService(db)
    return svc.get_analytics(ctx.tenant_id, ctx.workspace_id)


# ── Exports ────────────────────────────────────────────────────────

@platform_router.post("/platform/exports", status_code=201)
def create_export(
    body: ExportCreate,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.exports.service import ExportService
    svc = ExportService(db)
    job = svc.create_export(ctx.tenant_id, body.export_type, body.format, body.filters)
    return ExportOut.model_validate(job)


@platform_router.get("/platform/exports/{export_id}")
def get_export(
    export_id: int,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.exports.service import ExportService
    svc = ExportService(db)
    job = svc.get_export(export_id, ctx.tenant_id)
    if not job:
        raise HTTPException(404, "export not found")
    return ExportOut.model_validate(job)


# ── Widgets ────────────────────────────────────────────────────────

@platform_router.get("/platform/widgets", response_model=list[WidgetOut])
def list_widgets(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.platform_api.query import PlatformQueryService
    svc = PlatformQueryService(db)
    return svc.list_widgets(ctx.tenant_id, ctx.workspace_id)


@platform_router.post("/platform/widgets", response_model=WidgetOut, status_code=201)
def create_widget(
    body: WidgetCreate,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.platform_api.query import PlatformQueryService
    svc = PlatformQueryService(db)
    return svc.create_widget(
        ctx.tenant_id, body.name, body.widget_type, body.config,
        body.workspace_id or ctx.workspace_id, body.position,
    )


# ── Plugins ────────────────────────────────────────────────────────

@platform_router.get("/platform/plugins")
def list_plugins(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
):
    from scoring_service.plugins.registry import plugin_registry
    return plugin_registry.list_all()


@platform_router.get("/platform/plugins/health")
def plugins_health(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
):
    from scoring_service.plugins.registry import plugin_registry
    return plugin_registry.health()


# ── Plans ──────────────────────────────────────────────────────────

@platform_router.get("/platform/plans", response_model=list[PlanDefinitionOut])
def list_plans(
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db=Depends(_get_db),
):
    from scoring_service.db.models import PlanDefinition
    return db.query(PlanDefinition).all()


# ══ Admin Routes ═══════════════════════════════════════════════════

@platform_admin_router.get("/diagnostics")
def admin_diagnostics(
    request: Request,
    ctx: TenantContext = Depends(get_admin_context),
    db=Depends(_get_db),
):
    """Cross-tenant diagnostic summary."""
    from sqlalchemy import func
    from scoring_service.db.models import (
        Alert, PipelineEvent, ProcessingRun, Recommendation, Tenant, Trend,
    )

    tenant_count = db.query(func.count(Tenant.id)).scalar() or 0
    total_events = db.query(func.count(PipelineEvent.id)).scalar() or 0
    total_trends = db.query(func.count(Trend.id)).scalar() or 0
    total_recs = db.query(func.count(Recommendation.id)).scalar() or 0
    total_alerts = db.query(func.count(Alert.id)).scalar() or 0
    total_runs = db.query(func.count(ProcessingRun.id)).scalar() or 0

    # Per-tenant breakdown
    per_tenant = (
        db.query(
            Tenant.id, Tenant.name, Tenant.plan,
            func.count(Trend.id).label("trends"),
        )
        .outerjoin(Trend, Trend.tenant_id == Tenant.id)
        .group_by(Tenant.id, Tenant.name, Tenant.plan)
        .all()
    )

    return {
        "tenant_count": tenant_count,
        "total_events": total_events,
        "total_trends": total_trends,
        "total_recommendations": total_recs,
        "total_alerts": total_alerts,
        "total_runs": total_runs,
        "per_tenant": [
            {"id": t.id, "name": t.name, "plan": t.plan, "trends": t.trends}
            for t in per_tenant
        ],
    }


@platform_admin_router.get("/usage/all")
def admin_usage_all(
    request: Request,
    ctx: TenantContext = Depends(get_admin_context),
    db=Depends(_get_db),
):
    """Cross-tenant usage summary."""
    from scoring_service.db.models import Tenant
    from scoring_service.usage.service import UsageService
    svc = UsageService(db)
    tenants = db.query(Tenant).all()
    return {
        "tenants": [
            svc.get_summary(t.id) for t in tenants
        ],
    }
