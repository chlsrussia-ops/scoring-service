from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from scoring_service.db.models import ScoreRecord

class ScoreRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, request_id: str, source: str, payload: dict, final_score: float,
             capped: bool, used_fallback: bool, reason: str | None,
             review_label: str, approved: bool, diagnostics: list[str]) -> ScoreRecord:
        record = ScoreRecord(
            request_id=request_id, source=source, payload_json=payload,
            final_score=final_score, capped=capped, used_fallback=used_fallback,
            reason=reason, review_label=review_label, approved=approved,
            diagnostics_json=diagnostics, created_at=datetime.now(timezone.utc))
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_request_id(self, request_id: str) -> ScoreRecord | None:
        return self.db.query(ScoreRecord).filter(ScoreRecord.request_id == request_id).first()

    def list_recent(self, limit: int = 50) -> list[ScoreRecord]:
        return self.db.query(ScoreRecord).order_by(ScoreRecord.created_at.desc()).limit(limit).all()
