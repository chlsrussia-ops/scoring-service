"""Explanation / lineage / decision trace service."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from scoring_service.db.models import (
    DecisionTrace,
    SignalLineageLink,
    TrendEvidence,
)


class ExplanationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_trace(
        self, tenant_id: str, entity_type: str, entity_id: int,
    ) -> DecisionTrace | None:
        return (
            self.db.query(DecisionTrace)
            .filter(
                DecisionTrace.tenant_id == tenant_id,
                DecisionTrace.entity_type == entity_type,
                DecisionTrace.entity_id == entity_id,
            )
            .order_by(DecisionTrace.created_at.desc())
            .first()
        )

    def list_traces(
        self, tenant_id: str, entity_type: str | None = None,
        *, limit: int = 50, offset: int = 0,
    ) -> list[DecisionTrace]:
        q = self.db.query(DecisionTrace).filter(DecisionTrace.tenant_id == tenant_id)
        if entity_type:
            q = q.filter(DecisionTrace.entity_type == entity_type)
        return q.order_by(DecisionTrace.created_at.desc()).offset(offset).limit(limit).all()

    def get_lineage(
        self, tenant_id: str, entity_type: str, entity_id: int,
    ) -> list[SignalLineageLink]:
        """Get lineage links from/to an entity."""
        from_links = (
            self.db.query(SignalLineageLink)
            .filter(
                SignalLineageLink.tenant_id == tenant_id,
                SignalLineageLink.from_type == entity_type,
                SignalLineageLink.from_id == entity_id,
            )
            .all()
        )
        to_links = (
            self.db.query(SignalLineageLink)
            .filter(
                SignalLineageLink.tenant_id == tenant_id,
                SignalLineageLink.to_type == entity_type,
                SignalLineageLink.to_id == entity_id,
            )
            .all()
        )
        return from_links + to_links

    def get_evidence(self, trend_id: int) -> list[TrendEvidence]:
        return (
            self.db.query(TrendEvidence)
            .filter(TrendEvidence.trend_id == trend_id)
            .order_by(TrendEvidence.created_at.desc())
            .all()
        )

    def create_trace(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: int,
        *,
        policy_version_id: int | None = None,
        input_summary: dict[str, Any] | None = None,
        matched_rules: list[dict[str, Any]] | None = None,
        factor_contributions: dict[str, Any] | None = None,
        explanation_text: str | None = None,
        explanation_json: dict[str, Any] | None = None,
    ) -> DecisionTrace:
        trace = DecisionTrace(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            policy_version_id=policy_version_id,
            input_summary_json=input_summary or {},
            matched_rules_json=matched_rules or [],
            factor_contributions_json=factor_contributions or {},
            explanation_text=explanation_text,
            explanation_json=explanation_json or {},
        )
        self.db.add(trace)
        self.db.commit()
        self.db.refresh(trace)
        return trace

    def add_lineage(
        self,
        tenant_id: str,
        from_type: str,
        from_id: int,
        to_type: str,
        to_id: int,
        relationship: str = "derived_from",
    ) -> SignalLineageLink:
        link = SignalLineageLink(
            tenant_id=tenant_id,
            from_type=from_type,
            from_id=from_id,
            to_type=to_type,
            to_id=to_id,
            relationship_type=relationship,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link
