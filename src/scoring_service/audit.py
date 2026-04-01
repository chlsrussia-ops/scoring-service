"""Audit logging for critical admin and system actions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.correlation import get_correlation_id
from scoring_service.db.models import AuditLog

logger = logging.getLogger("scoring_service")


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            correlation_id=get_correlation_id(),
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        self.db.flush()
        logger.info(
            "audit actor=%s action=%s target=%s/%s",
            actor, action, target_type, target_id,
        )
        return entry

    def list_recent(
        self,
        action: str | None = None,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        q = self.db.query(AuditLog)
        if action:
            q = q.filter(AuditLog.action == action)
        if target_type:
            q = q.filter(AuditLog.target_type == target_type)
        return q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
