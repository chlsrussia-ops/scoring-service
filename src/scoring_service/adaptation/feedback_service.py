"""Feedback & Outcome ingestion service."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import FeedbackRepository, OutcomeRepository
from scoring_service.config import Settings
from scoring_service.db.models import FeedbackEvent, OutcomeRecord

logger = logging.getLogger("scoring_service")


class FeedbackService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.feedback_repo = FeedbackRepository(db)
        self.outcome_repo = OutcomeRepository(db)

    def record_feedback(
        self, tenant_id: str, target_type: str, target_id: int,
        feedback_type: str, label: str, *,
        score: float | None = None, usefulness_rating: int | None = None,
        confidence_rating: float | None = None, reviewer: str = "human",
        source: str = "human", evidence_snapshot: dict | None = None,
        metadata: dict | None = None,
    ) -> FeedbackEvent:
        fb = self.feedback_repo.create(
            tenant_id=tenant_id, target_type=target_type, target_id=target_id,
            feedback_type=feedback_type, label=label,
            score=score, usefulness_rating=usefulness_rating,
            confidence_rating=confidence_rating, reviewer=reviewer,
            source=source, evidence_snapshot=evidence_snapshot,
            metadata_json=metadata or {},
        )
        logger.info(
            "feedback_recorded id=%s tenant=%s target=%s/%s label=%s",
            fb.id, tenant_id, target_type, target_id, label,
        )
        return fb

    def record_outcome(
        self, tenant_id: str, entity_type: str, entity_id: int,
        outcome_type: str, *,
        outcome_value: str | None = None,
        measurement_window_hours: int = 24,
        confidence: float = 0.5, evidence: dict | None = None,
    ) -> OutcomeRecord:
        rec = self.outcome_repo.create(
            tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
            outcome_type=outcome_type, outcome_value=outcome_value,
            measurement_window_hours=measurement_window_hours,
            confidence=confidence, evidence_json=evidence or {},
        )
        logger.info(
            "outcome_recorded id=%s tenant=%s entity=%s/%s type=%s",
            rec.id, tenant_id, entity_type, entity_id, outcome_type,
        )
        return rec

    def list_feedback(
        self, tenant_id: str, limit: int = 100, offset: int = 0
    ) -> list[FeedbackEvent]:
        return self.feedback_repo.list_by_tenant(tenant_id, limit=limit, offset=offset)

    def list_outcomes(
        self, tenant_id: str, since: datetime | None = None,
        entity_type: str | None = None, limit: int = 200,
    ) -> list[OutcomeRecord]:
        if since is None:
            from datetime import timedelta
            since = datetime.now(timezone.utc) - timedelta(days=30)
        return self.outcome_repo.list_by_tenant(tenant_id, since, entity_type, limit)
