"""Platform query service — tenant-scoped queries with filtering/pagination."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from scoring_service.db.models import (
    Alert,
    PipelineEvent,
    Recommendation,
    Signal,
    Trend,
    WidgetConfig,
)


class PlatformQueryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Trends ──────────────────────────────────────────────

    def query_trends(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        category: str | None = None,
        source: str | None = None,
        topic: str | None = None,
        direction: str | None = None,
        min_score: float | None = None,
        sort_by: str = "score",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Trend], int]:
        q = self.db.query(Trend).filter(Trend.tenant_id == tenant_id)
        if workspace_id:
            q = q.filter(Trend.workspace_id == workspace_id)
        if category:
            q = q.filter(Trend.category == category)
        if source:
            q = q.filter(Trend.source == source)
        if topic:
            q = q.filter(Trend.topic.ilike(f"%{topic}%"))
        if direction:
            q = q.filter(Trend.direction == direction)
        if min_score is not None:
            q = q.filter(Trend.score >= min_score)

        total = q.count()

        sort_col = getattr(Trend, sort_by, Trend.score)
        if sort_dir == "asc":
            q = q.order_by(sort_col.asc())
        else:
            q = q.order_by(sort_col.desc())

        items = q.offset(offset).limit(limit).all()
        return items, total

    # ── Signals ─────────────────────────────────────────────

    def query_signals(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        category: str | None = None,
        source: str | None = None,
        topic: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Signal], int]:
        q = self.db.query(Signal).filter(Signal.tenant_id == tenant_id)
        if workspace_id:
            q = q.filter(Signal.workspace_id == workspace_id)
        if category:
            q = q.filter(Signal.category == category)
        if source:
            q = q.filter(Signal.source == source)
        if topic:
            q = q.filter(Signal.topic.ilike(f"%{topic}%"))

        total = q.count()
        items = q.order_by(Signal.detected_at.desc()).offset(offset).limit(limit).all()
        return items, total

    # ── Recommendations ─────────────────────────────────────

    def query_recommendations(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Recommendation], int]:
        q = self.db.query(Recommendation).filter(Recommendation.tenant_id == tenant_id)
        if workspace_id:
            q = q.filter(Recommendation.workspace_id == workspace_id)
        if category:
            q = q.filter(Recommendation.category == category)
        if priority:
            q = q.filter(Recommendation.priority == priority)
        if status:
            q = q.filter(Recommendation.status == status)

        total = q.count()
        items = q.order_by(Recommendation.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    # ── Alerts ──────────────────────────────────────────────

    def query_alerts(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        alert_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        q = self.db.query(Alert).filter(Alert.tenant_id == tenant_id)
        if workspace_id:
            q = q.filter(Alert.workspace_id == workspace_id)
        if severity:
            q = q.filter(Alert.severity == severity)
        if status:
            q = q.filter(Alert.status == status)
        if alert_type:
            q = q.filter(Alert.alert_type == alert_type)

        total = q.count()
        items = q.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    # ── Events ──────────────────────────────────────────────

    def query_events(
        self,
        tenant_id: str,
        *,
        source: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PipelineEvent], int]:
        q = self.db.query(PipelineEvent).filter(PipelineEvent.tenant_id == tenant_id)
        if source:
            q = q.filter(PipelineEvent.source == source)
        if event_type:
            q = q.filter(PipelineEvent.event_type == event_type)

        total = q.count()
        items = q.order_by(PipelineEvent.ingested_at.desc()).offset(offset).limit(limit).all()
        return items, total

    # ── Analytics ───────────────────────────────────────────

    def get_analytics(
        self, tenant_id: str, workspace_id: str | None = None,
    ) -> dict[str, Any]:
        def _count(model: Any, extra_filter: Any = None) -> int:
            q = self.db.query(func.count(model.id)).filter(model.tenant_id == tenant_id)
            if workspace_id and hasattr(model, "workspace_id"):
                q = q.filter(model.workspace_id == workspace_id)
            if extra_filter is not None:
                q = q.filter(extra_filter)
            return q.scalar() or 0

        total_events = _count(PipelineEvent)
        total_signals = _count(Signal)
        total_trends = _count(Trend)
        total_recs = _count(Recommendation)
        total_alerts = _count(Alert)

        # Top categories
        top_cats = (
            self.db.query(Trend.category, func.count(Trend.id).label("cnt"))
            .filter(Trend.tenant_id == tenant_id)
            .group_by(Trend.category)
            .order_by(func.count(Trend.id).desc())
            .limit(10).all()
        )

        # Top sources
        top_sources = (
            self.db.query(PipelineEvent.source, func.count(PipelineEvent.id).label("cnt"))
            .filter(PipelineEvent.tenant_id == tenant_id)
            .group_by(PipelineEvent.source)
            .order_by(func.count(PipelineEvent.id).desc())
            .limit(10).all()
        )

        return {
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "total_events": total_events,
            "total_signals": total_signals,
            "total_trends": total_trends,
            "total_recommendations": total_recs,
            "total_alerts": total_alerts,
            "top_categories": [{"category": c, "count": n} for c, n in top_cats],
            "top_sources": [{"source": s, "count": n} for s, n in top_sources],
        }

    # ── Widgets ─────────────────────────────────────────────

    def list_widgets(
        self, tenant_id: str, workspace_id: str | None = None,
    ) -> list[WidgetConfig]:
        q = self.db.query(WidgetConfig).filter(WidgetConfig.tenant_id == tenant_id)
        if workspace_id:
            q = q.filter(WidgetConfig.workspace_id == workspace_id)
        return q.order_by(WidgetConfig.position).all()

    def create_widget(
        self,
        tenant_id: str,
        name: str,
        widget_type: str,
        config: dict[str, Any],
        workspace_id: str | None = None,
        position: int = 0,
    ) -> WidgetConfig:
        w = WidgetConfig(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
            widget_type=widget_type,
            config_json=config,
            position=position,
        )
        self.db.add(w)
        self.db.commit()
        self.db.refresh(w)
        return w
