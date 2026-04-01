"""Transactional outbox pattern v2 — with dedup_key support."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import DeliveryAttempt, OutboxEvent

logger = logging.getLogger("scoring_service")

PENDING = "pending"
DISPATCHED = "dispatched"
FAILED = "failed"


class OutboxService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    @staticmethod
    def compute_dedup_key(event_type: str, aggregate_type: str, aggregate_id: str) -> str:
        raw = f"{event_type}:{aggregate_type}:{aggregate_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def publish(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        dedup_key: str | None = None,
    ) -> OutboxEvent:
        """Write event to outbox within current transaction. Dedup prevents duplicates."""
        key = dedup_key or self.compute_dedup_key(event_type, aggregate_type, aggregate_id)

        # Check for existing event with same dedup_key
        existing = (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.dedup_key == key)
            .first()
        )
        if existing:
            logger.debug("outbox_dedup_hit key=%s event_id=%s", key, existing.id)
            return existing

        event = OutboxEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status=PENDING,
            dedup_key=key,
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(event)
        self.db.flush()
        logger.info(
            "outbox_publish event_id=%s type=%s aggregate=%s/%s dedup=%s",
            event.id, event_type, aggregate_type, aggregate_id, key,
        )
        return event

    def fetch_pending(self, batch_size: int | None = None) -> list[OutboxEvent]:
        size = batch_size or self.settings.outbox_batch_size
        return (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.status == PENDING)
            .order_by(OutboxEvent.created_at.asc())
            .limit(size)
            .all()
        )

    def mark_dispatched(self, event: OutboxEvent) -> None:
        now = datetime.now(timezone.utc)
        event.status = DISPATCHED
        event.dispatched_at = now
        event.dispatch_attempts += 1
        self.db.flush()

    def mark_failed(self, event: OutboxEvent, error: str) -> None:
        event.dispatch_attempts += 1
        event.dispatch_error = error[:500]
        if event.dispatch_attempts >= self.settings.outbox_max_dispatch_attempts:
            event.status = FAILED
            logger.warning(
                "outbox_event_dead event_id=%s attempts=%s",
                event.id, event.dispatch_attempts,
            )
        self.db.flush()

    def record_delivery_attempt(
        self,
        event: OutboxEvent,
        channel: str,
        status: str,
        error: str | None = None,
        response_code: int | None = None,
    ) -> DeliveryAttempt:
        attempt = DeliveryAttempt(
            outbox_event_id=event.id,
            channel=channel,
            status=status,
            error=error[:500] if error else None,
            response_code=response_code,
            attempted_at=datetime.now(timezone.utc),
        )
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def dispatch_single(self, event_id: int) -> OutboxEvent | None:
        event = self.db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        if not event:
            return None
        event.status = PENDING
        event.dispatch_error = None
        self.db.flush()
        return event

    def list_events(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OutboxEvent]:
        q = self.db.query(OutboxEvent)
        if status:
            q = q.filter(OutboxEvent.status == status)
        return q.order_by(OutboxEvent.created_at.desc()).offset(offset).limit(limit).all()

    def count_pending(self) -> int:
        return self.db.query(OutboxEvent).filter(OutboxEvent.status == PENDING).count()

    def count_failed(self) -> int:
        return self.db.query(OutboxEvent).filter(OutboxEvent.status == FAILED).count()
