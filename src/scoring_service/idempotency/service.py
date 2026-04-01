"""Idempotency service — prevents duplicate processing of requests."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import IdempotencyRecord


class IdempotencyService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    @staticmethod
    def compute_hash(payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:64]

    def check(self, key: str, operation: str, payload: Any) -> IdempotencyRecord | None:
        """Return existing record if key was already processed and not expired."""
        now = datetime.now(timezone.utc)
        record = (
            self.db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.expires_at > now,
            )
            .first()
        )
        return record

    def start(self, key: str, operation: str, payload: Any) -> IdempotencyRecord:
        """Mark key as processing. Returns new record."""
        now = datetime.now(timezone.utc)
        request_hash = self.compute_hash(payload)
        record = IdempotencyRecord(
            idempotency_key=key,
            operation=operation,
            status="processing",
            request_hash=request_hash,
            created_at=now,
            expires_at=now + timedelta(seconds=self.settings.idempotency_ttl_seconds),
        )
        self.db.add(record)
        self.db.flush()
        return record

    def complete(
        self,
        record: IdempotencyRecord,
        response_status: int,
        response_body: dict,
    ) -> None:
        """Mark idempotency record as completed with response."""
        record.status = "completed"
        record.response_status = response_status
        record.response_body = response_body
        self.db.flush()

    def fail(self, record: IdempotencyRecord, error: str) -> None:
        """Mark as failed so it can be retried."""
        record.status = "failed"
        record.response_body = {"error": error}
        self.db.flush()

    def cleanup_expired(self) -> int:
        """Remove expired idempotency records. Returns count deleted."""
        now = datetime.now(timezone.utc)
        count = (
            self.db.query(IdempotencyRecord)
            .filter(IdempotencyRecord.expires_at <= now)
            .delete()
        )
        self.db.commit()
        return count
