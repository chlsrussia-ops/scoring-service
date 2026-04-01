"""Dashboard API routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from scoring_service.db.models import (
    Alert, DataSource, DemoRun, LlmGeneration,
    PipelineEvent, Recommendation, Signal, Trend,
)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


def _get_db(request: Request) -> Session:
    return request.app.state.session_factory()


def _tenant_id(request: Request) -> str:
    return request.query_params.get("tenant_id", "demo")


@router.get("/overview")
async def overview(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        events_total = db.query(PipelineEvent).filter(PipelineEvent.tenant_id == tid).count()
        trends_total = db.query(Trend).filter(Trend.tenant_id == tid).count()
        trends_rising = db.query(Trend).filter(Trend.tenant_id == tid, Trend.direction == "rising").count()
        recs_total = db.query(Recommendation).filter(Recommendation.tenant_id == tid).count()
        recs_high = db.query(Recommendation).filter(Recommendation.tenant_id == tid, Recommendation.priority == "high").count()
        alerts_total = db.query(Alert).filter(Alert.tenant_id == tid).count()
        alerts_open = db.query(Alert).filter(Alert.tenant_id == tid, Alert.status == "open").count()
        sources_total = db.query(DataSource).filter(DataSource.tenant_id == tid).count()
        sources_active = db.query(DataSource).filter(DataSource.tenant_id == tid, DataSource.status == "active").count()
        return {
            "events": {"total": events_total},
            "trends": {"total": trends_total, "rising": trends_rising},
            "recommendations": {"total": recs_total, "high_priority": recs_high},
            "alerts": {"total": alerts_total, "open": alerts_open},
            "sources": {"total": sources_total, "active": sources_active},
        }
    finally:
        db.close()


@router.get("/activity")
async def activity(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        recent_events = db.query(PipelineEvent).filter(
            PipelineEvent.tenant_id == tid
        ).order_by(PipelineEvent.ingested_at.desc()).limit(20).all()
        recent_runs = db.query(DemoRun).filter(
            DemoRun.tenant_id == tid
        ).order_by(DemoRun.started_at.desc()).limit(10).all()
        return {
            "recent_events": [
                {"id": e.id, "source": e.source, "event_type": e.event_type,
                 "title": (e.normalized_json or {}).get("title", ""),
                 "ingested_at": str(e.ingested_at)}
                for e in recent_events
            ],
            "recent_runs": [
                {"id": r.id, "action": r.action, "status": r.status, "started_at": str(r.started_at)}
                for r in recent_runs
            ],
        }
    finally:
        db.close()


@router.get("/trends")
async def trends_list(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        sort = request.query_params.get("sort", "score")
        direction = request.query_params.get("direction", "desc")
        category = request.query_params.get("category")
        limit = min(int(request.query_params.get("limit", "50")), 200)
        offset = int(request.query_params.get("offset", "0"))

        q = db.query(Trend).filter(Trend.tenant_id == tid)
        if category:
            q = q.filter(Trend.category == category)

        sort_col = getattr(Trend, sort, Trend.score)
        if direction == "asc":
            q = q.order_by(sort_col.asc())
        else:
            q = q.order_by(sort_col.desc())

        total = q.count()
        items = q.offset(offset).limit(limit).all()

        # Get LLM summaries for these trends
        trend_ids = [t.id for t in items]
        generations = {}
        if trend_ids:
            gens = db.query(LlmGeneration).filter(
                LlmGeneration.tenant_id == tid,
                LlmGeneration.entity_type == "trend",
                LlmGeneration.entity_id.in_(trend_ids),
            ).all()
            for g in gens:
                generations[g.entity_id] = g.output_text

        return {
            "total": total,
            "items": [
                {
                    "id": t.id, "topic": t.topic, "category": t.category,
                    "score": t.score, "confidence": t.confidence,
                    "direction": t.direction, "event_count": t.event_count,
                    "growth_rate": t.growth_rate, "source": t.source,
                    "first_seen": str(t.first_seen), "last_seen": str(t.last_seen),
                    "ai_summary": generations.get(t.id),
                }
                for t in items
            ],
        }
    finally:
        db.close()


@router.get("/trends/{trend_id}")
async def trend_detail(trend_id: int, request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        trend = db.query(Trend).filter(Trend.id == trend_id, Trend.tenant_id == tid).first()
        if not trend:
            return {"error": "Trend not found"}

        # Get linked recommendations
        recs = db.query(Recommendation).filter(
            Recommendation.tenant_id == tid,
            Recommendation.trend_id == trend_id,
        ).all()

        # Get linked alerts
        alerts = db.query(Alert).filter(
            Alert.tenant_id == tid,
            Alert.trend_id == trend_id,
        ).all()

        # Get LLM summary
        gen = db.query(LlmGeneration).filter(
            LlmGeneration.tenant_id == tid,
            LlmGeneration.entity_type == "trend",
            LlmGeneration.entity_id == trend_id,
        ).first()

        # Get related events by category
        related_events = db.query(PipelineEvent).filter(
            PipelineEvent.tenant_id == tid,
        ).order_by(PipelineEvent.ingested_at.desc()).limit(10).all()

        return {
            "id": trend.id,
            "topic": trend.topic,
            "category": trend.category,
            "score": trend.score,
            "confidence": trend.confidence,
            "direction": trend.direction,
            "event_count": trend.event_count,
            "growth_rate": trend.growth_rate,
            "source": trend.source,
            "first_seen": str(trend.first_seen),
            "last_seen": str(trend.last_seen),
            "metadata": trend.metadata_json,
            "ai_summary": gen.output_text if gen else None,
            "recommendations": [
                {"id": r.id, "title": r.title, "priority": r.priority, "confidence": r.confidence}
                for r in recs
            ],
            "alerts": [
                {"id": a.id, "title": a.title, "severity": a.severity, "status": a.status}
                for a in alerts
            ],
            "related_events": [
                {"id": e.id, "title": (e.normalized_json or {}).get("title", ""), "source": e.source}
                for e in related_events
            ],
        }
    finally:
        db.close()


@router.get("/recommendations")
async def recommendations_list(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        limit = min(int(request.query_params.get("limit", "50")), 200)
        offset = int(request.query_params.get("offset", "0"))
        priority = request.query_params.get("priority")

        q = db.query(Recommendation).filter(Recommendation.tenant_id == tid)
        if priority:
            q = q.filter(Recommendation.priority == priority)
        q = q.order_by(Recommendation.created_at.desc())

        total = q.count()
        items = q.offset(offset).limit(limit).all()

        # Get LLM enhancements
        rec_ids = [r.id for r in items]
        enhancements = {}
        if rec_ids:
            gens = db.query(LlmGeneration).filter(
                LlmGeneration.tenant_id == tid,
                LlmGeneration.entity_type == "recommendation",
                LlmGeneration.entity_id.in_(rec_ids),
            ).all()
            for g in gens:
                enhancements[g.entity_id] = g.output_text

        return {
            "total": total,
            "items": [
                {
                    "id": r.id, "title": r.title, "body": r.body,
                    "category": r.category, "priority": r.priority,
                    "confidence": r.confidence, "status": r.status,
                    "trend_id": r.trend_id,
                    "created_at": str(r.created_at),
                    "ai_enhancement": enhancements.get(r.id),
                }
                for r in items
            ],
        }
    finally:
        db.close()


@router.get("/alerts")
async def alerts_list(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        limit = min(int(request.query_params.get("limit", "50")), 200)
        q = db.query(Alert).filter(Alert.tenant_id == tid).order_by(Alert.created_at.desc())
        total = q.count()
        items = q.limit(limit).all()
        return {
            "total": total,
            "items": [
                {
                    "id": a.id, "title": a.title, "alert_type": a.alert_type,
                    "severity": a.severity, "status": a.status, "body": a.body,
                    "trend_id": a.trend_id, "created_at": str(a.created_at),
                    "acknowledged_at": str(a.acknowledged_at) if a.acknowledged_at else None,
                }
                for a in items
            ],
        }
    finally:
        db.close()


@router.get("/sources")
async def sources_list(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        items = db.query(DataSource).filter(DataSource.tenant_id == tid).all()
        return {
            "total": len(items),
            "items": [
                {
                    "id": s.id, "name": s.name,
                    "source_type": s.source_type.value if hasattr(s.source_type, "value") else s.source_type,
                    "status": s.status.value if hasattr(s.status, "value") else s.status,
                    "enabled": s.enabled,
                    "items_fetched": s.items_fetched,
                    "items_normalized": s.items_normalized,
                    "failure_count": s.failure_count,
                    "last_sync_at": str(s.last_sync_at) if s.last_sync_at else None,
                    "last_error": s.last_error,
                    "created_at": str(s.created_at),
                }
                for s in items
            ],
        }
    finally:
        db.close()
