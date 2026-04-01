"""Export service — generates JSON/CSV exports."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.db.models import (
    Alert,
    ExportJob,
    PipelineEvent,
    Recommendation,
    RunStatus,
    Signal,
    Trend,
)


class ExportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_export(
        self,
        tenant_id: str,
        export_type: str,
        fmt: str = "json",
        filters: dict[str, Any] | None = None,
    ) -> ExportJob:
        job = ExportJob(
            tenant_id=tenant_id,
            export_type=export_type,
            format=fmt,
            filters_json=filters or {},
        )
        self.db.add(job)
        self.db.flush()

        try:
            data = self._fetch_data(tenant_id, export_type, filters or {})
            if fmt == "csv":
                result = self._to_csv(data)
            else:
                result = data

            job.result_json = {"data": result, "count": len(data)}  # type: ignore[assignment]
            job.status = RunStatus.completed  # type: ignore[assignment]
            job.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        except Exception as e:
            job.status = RunStatus.failed  # type: ignore[assignment]
            job.result_json = {"error": str(e)}  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(job)
        return job

    def get_export(self, export_id: int, tenant_id: str) -> ExportJob | None:
        job = self.db.get(ExportJob, export_id)
        if job and job.tenant_id == tenant_id:
            return job
        return None

    def list_exports(self, tenant_id: str, *, limit: int = 20) -> list[ExportJob]:
        return (
            self.db.query(ExportJob)
            .filter(ExportJob.tenant_id == tenant_id)
            .order_by(ExportJob.created_at.desc())
            .limit(limit).all()
        )

    def _fetch_data(
        self, tenant_id: str, export_type: str, filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        limit = min(filters.get("limit", 1000), 10000)

        if export_type == "trends":
            q = self.db.query(Trend).filter(Trend.tenant_id == tenant_id)
            if filters.get("category"):
                q = q.filter(Trend.category == filters["category"])
            items = q.order_by(Trend.score.desc()).limit(limit).all()
            return [
                {
                    "id": t.id, "topic": t.topic, "category": t.category,
                    "source": t.source, "score": t.score, "confidence": t.confidence,
                    "direction": t.direction, "event_count": t.event_count,
                }
                for t in items
            ]

        if export_type == "signals":
            items = (
                self.db.query(Signal)
                .filter(Signal.tenant_id == tenant_id)
                .order_by(Signal.detected_at.desc())
                .limit(limit).all()
            )
            return [
                {
                    "id": s.id, "topic": s.topic, "category": s.category,
                    "source": s.source, "value": s.value,
                }
                for s in items
            ]

        if export_type == "recommendations":
            items = (
                self.db.query(Recommendation)
                .filter(Recommendation.tenant_id == tenant_id)
                .order_by(Recommendation.created_at.desc())
                .limit(limit).all()
            )
            return [
                {
                    "id": r.id, "title": r.title, "category": r.category,
                    "priority": r.priority, "confidence": r.confidence,
                }
                for r in items
            ]

        if export_type == "alerts":
            items = (
                self.db.query(Alert)
                .filter(Alert.tenant_id == tenant_id)
                .order_by(Alert.created_at.desc())
                .limit(limit).all()
            )
            return [
                {
                    "id": a.id, "title": a.title, "alert_type": a.alert_type,
                    "severity": a.severity, "status": a.status,
                }
                for a in items
            ]

        if export_type == "events":
            items = (
                self.db.query(PipelineEvent)
                .filter(PipelineEvent.tenant_id == tenant_id)
                .order_by(PipelineEvent.ingested_at.desc())
                .limit(limit).all()
            )
            return [
                {
                    "id": e.id, "source": e.source, "event_type": e.event_type,
                    "external_id": e.external_id,
                }
                for e in items
            ]

        return []

    def _to_csv(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert to CSV-like list of dicts (actual CSV generation would be at response level)."""
        return data
