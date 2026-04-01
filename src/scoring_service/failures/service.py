"""Failure handling / Dead Letter service."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import DeadLetterItem, FailureRecord

logger = logging.getLogger("scoring_service")


class FailureService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def record_failure(
        self,
        entity_type: str,
        entity_id: str,
        operation: str,
        error: str,
        payload_snapshot: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> FailureRecord:
        rec = FailureRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            error=error,
            payload_snapshot=payload_snapshot,
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(rec)
        self.db.flush()
        logger.warning(
            "failure_recorded entity=%s/%s op=%s error=%s",
            entity_type, entity_id, operation, error[:200],
        )
        return rec

    def to_dead_letter(
        self,
        source_type: str,
        source_id: str,
        operation: str,
        payload_snapshot: dict[str, Any],
        error: str,
        correlation_id: str | None = None,
    ) -> DeadLetterItem:
        item = DeadLetterItem(
            source_type=source_type,
            source_id=source_id,
            operation=operation,
            payload_snapshot=payload_snapshot,
            error=error,
            retry_count=0,
            retry_history=[],
            status="failed",
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(item)
        self.db.flush()
        logger.warning(
            "dead_letter source=%s/%s op=%s", source_type, source_id, operation
        )
        return item

    def list_dead_letter(
        self,
        source_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeadLetterItem]:
        q = self.db.query(DeadLetterItem)
        if source_type:
            q = q.filter(DeadLetterItem.source_type == source_type)
        if status:
            q = q.filter(DeadLetterItem.status == status)
        return q.order_by(DeadLetterItem.created_at.desc()).offset(offset).limit(limit).all()

    def list_failures(
        self,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FailureRecord]:
        q = self.db.query(FailureRecord)
        if entity_type:
            q = q.filter(FailureRecord.entity_type == entity_type)
        return q.order_by(FailureRecord.created_at.desc()).offset(offset).limit(limit).all()

    def get_dead_letter_item(self, item_id: int) -> DeadLetterItem | None:
        return self.db.query(DeadLetterItem).filter(DeadLetterItem.id == item_id).first()

    def replay_dead_letter(self, item_id: int) -> DeadLetterItem | None:
        """Reset a dead-letter item for replay."""
        item = self.get_dead_letter_item(item_id)
        if not item:
            return None
        now = datetime.now(timezone.utc)
        history = list(item.retry_history or [])
        history.append({
            "at": now.isoformat(),
            "prev_status": item.status,
            "prev_error": item.error,
        })
        item.status = "retrying"
        item.retry_count += 1
        item.retry_history = history
        self.db.flush()
        logger.info("dead_letter_replay item_id=%s", item_id)
        return item

    def count_by_status(self) -> dict[str, int]:
        from sqlalchemy import func
        rows = (
            self.db.query(DeadLetterItem.status, func.count())
            .group_by(DeadLetterItem.status)
            .all()
        )
        return {status: cnt for status, cnt in rows}
