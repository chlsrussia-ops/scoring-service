"""Source health tracking, quarantine, and backpressure."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import QuarantineRule, SourceHealthState

logger = logging.getLogger("scoring_service")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    """Make a datetime timezone-aware (UTC) if it's naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SourceProtectionService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def _get_or_create(self, source_name: str) -> SourceHealthState:
        state = (
            self.db.query(SourceHealthState)
            .filter(SourceHealthState.source_name == source_name)
            .first()
        )
        if not state:
            now = _utcnow()
            state = SourceHealthState(
                source_name=source_name,
                created_at=now,
                updated_at=now,
            )
            self.db.add(state)
            self.db.flush()
        return state

    def record_success(self, source_name: str) -> None:
        state = self._get_or_create(source_name)
        now = _utcnow()
        state.total_requests += 1
        state.consecutive_failures = 0
        state.last_success_at = now
        state.updated_at = now
        self.db.flush()

    def record_failure(self, source_name: str, error: str) -> None:
        state = self._get_or_create(source_name)
        now = _utcnow()
        state.total_requests += 1
        state.total_errors += 1
        state.consecutive_failures += 1
        state.last_error = error[:500]
        state.last_error_at = now
        state.updated_at = now

        threshold = self.settings.source_quarantine_error_threshold
        if state.consecutive_failures >= threshold and not self.is_quarantined(source_name):
            duration = self.settings.source_quarantine_duration_seconds
            state.quarantined_until = now + timedelta(seconds=duration)
            state.quarantine_reason = (
                f"auto: {state.consecutive_failures} consecutive failures"
            )
            logger.warning(
                "source_auto_quarantine source=%s failures=%s until=%s",
                source_name, state.consecutive_failures, state.quarantined_until,
            )
        self.db.flush()

    def is_quarantined(self, source_name: str) -> bool:
        state = (
            self.db.query(SourceHealthState)
            .filter(SourceHealthState.source_name == source_name)
            .first()
        )
        if not state or not state.quarantined_until:
            return False
        now = _utcnow()
        quarantined_until = _ensure_aware(state.quarantined_until)
        if quarantined_until <= now:
            state.quarantined_until = None
            state.quarantine_reason = None
            self.db.flush()
            return False
        return True

    def quarantine(
        self,
        source_name: str,
        reason: str,
        duration_seconds: int | None = None,
        created_by: str = "admin",
    ) -> SourceHealthState:
        state = self._get_or_create(source_name)
        now = _utcnow()
        dur = duration_seconds or self.settings.source_quarantine_duration_seconds
        state.quarantined_until = now + timedelta(seconds=dur)
        state.quarantine_reason = reason
        state.updated_at = now

        rule = QuarantineRule(
            source_name=source_name,
            reason=reason,
            quarantined_at=now,
            quarantined_until=state.quarantined_until,
            created_by=created_by,
            active=True,
        )
        self.db.add(rule)
        self.db.flush()
        logger.info("source_quarantined source=%s reason=%s by=%s", source_name, reason, created_by)
        return state

    def resume(self, source_name: str) -> SourceHealthState | None:
        state = (
            self.db.query(SourceHealthState)
            .filter(SourceHealthState.source_name == source_name)
            .first()
        )
        if not state:
            return None
        now = _utcnow()
        state.quarantined_until = None
        state.quarantine_reason = None
        state.consecutive_failures = 0
        state.updated_at = now

        self.db.query(QuarantineRule).filter(
            QuarantineRule.source_name == source_name,
            QuarantineRule.active.is_(True),
        ).update({"active": False})
        self.db.flush()
        logger.info("source_resumed source=%s", source_name)
        return state

    def get_health(self, source_name: str) -> SourceHealthState | None:
        return (
            self.db.query(SourceHealthState)
            .filter(SourceHealthState.source_name == source_name)
            .first()
        )

    def list_all(self) -> list[SourceHealthState]:
        return (
            self.db.query(SourceHealthState)
            .order_by(SourceHealthState.source_name)
            .all()
        )

    def list_quarantined(self) -> list[SourceHealthState]:
        now = _utcnow()
        all_sources = self.db.query(SourceHealthState).filter(
            SourceHealthState.quarantined_until.isnot(None)
        ).all()
        return [
            s for s in all_sources
            if s.quarantined_until and _ensure_aware(s.quarantined_until) > now
        ]

    def summary(self) -> dict:
        all_sources = self.list_all()
        now = _utcnow()
        quarantined = [
            s for s in all_sources
            if s.quarantined_until and _ensure_aware(s.quarantined_until) > now
        ]
        unhealthy = [
            s for s in all_sources
            if s.consecutive_failures >= 3 and s not in quarantined
        ]
        return {
            "total_sources": len(all_sources),
            "healthy": len(all_sources) - len(quarantined) - len(unhealthy),
            "unhealthy": len(unhealthy),
            "quarantined": len(quarantined),
            "sources": [
                {
                    "name": s.source_name,
                    "total_requests": s.total_requests,
                    "total_errors": s.total_errors,
                    "consecutive_failures": s.consecutive_failures,
                    "quarantined_until": (
                        _ensure_aware(s.quarantined_until).isoformat()
                        if s.quarantined_until and _ensure_aware(s.quarantined_until) > now
                        else None
                    ),
                    "error_rate": round(s.total_errors / max(s.total_requests, 1), 4),
                }
                for s in all_sources
            ],
        }
