"""Repositories for all adaptation entities."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from scoring_service.db.models import (
    AdaptationExperiment,
    AdaptationProposal,
    AdaptationVersion,
    AdaptiveScoringLog,
    AdaptiveScoringProfile,
    EvaluationRun,
    FeedbackEvent,
    GoalDefinition,
    MetricSnapshot,
    OptimizationRun,
    OutcomeRecord,
    RollbackRecord,
    SelfEvaluationReport,
    SourceTrustCurrent,
    SourceTrustHistory,
)


class FeedbackRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs: Any) -> FeedbackEvent:
        fb = FeedbackEvent(**kwargs)
        self.db.add(fb)
        self.db.flush()
        return fb

    def get(self, feedback_id: int) -> FeedbackEvent | None:
        return self.db.get(FeedbackEvent, feedback_id)

    def list_by_target(
        self, target_type: str, target_id: int, limit: int = 50
    ) -> list[FeedbackEvent]:
        return (
            self.db.query(FeedbackEvent)
            .filter(FeedbackEvent.target_type == target_type, FeedbackEvent.target_id == target_id)
            .order_by(FeedbackEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_by_tenant(
        self, tenant_id: str, limit: int = 100, offset: int = 0
    ) -> list[FeedbackEvent]:
        return (
            self.db.query(FeedbackEvent)
            .filter(FeedbackEvent.tenant_id == tenant_id)
            .order_by(FeedbackEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_by_label(
        self, tenant_id: str, target_type: str, since: datetime
    ) -> dict[str, int]:
        rows = (
            self.db.query(FeedbackEvent.label, func.count())
            .filter(
                FeedbackEvent.tenant_id == tenant_id,
                FeedbackEvent.target_type == target_type,
                FeedbackEvent.created_at >= since,
            )
            .group_by(FeedbackEvent.label)
            .all()
        )
        return {label: cnt for label, cnt in rows}


class OutcomeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs: Any) -> OutcomeRecord:
        rec = OutcomeRecord(**kwargs)
        self.db.add(rec)
        self.db.flush()
        return rec

    def list_by_entity(
        self, entity_type: str, entity_id: int, limit: int = 50
    ) -> list[OutcomeRecord]:
        return (
            self.db.query(OutcomeRecord)
            .filter(OutcomeRecord.entity_type == entity_type, OutcomeRecord.entity_id == entity_id)
            .order_by(OutcomeRecord.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_by_type(
        self, tenant_id: str, entity_type: str, since: datetime
    ) -> dict[str, int]:
        rows = (
            self.db.query(OutcomeRecord.outcome_type, func.count())
            .filter(
                OutcomeRecord.tenant_id == tenant_id,
                OutcomeRecord.entity_type == entity_type,
                OutcomeRecord.created_at >= since,
            )
            .group_by(OutcomeRecord.outcome_type)
            .all()
        )
        return {otype: cnt for otype, cnt in rows}

    def list_by_tenant(
        self, tenant_id: str, since: datetime, entity_type: str | None = None, limit: int = 500
    ) -> list[OutcomeRecord]:
        q = self.db.query(OutcomeRecord).filter(
            OutcomeRecord.tenant_id == tenant_id,
            OutcomeRecord.created_at >= since,
        )
        if entity_type:
            q = q.filter(OutcomeRecord.entity_type == entity_type)
        return q.order_by(OutcomeRecord.created_at.desc()).limit(limit).all()


class EvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(self, **kwargs: Any) -> EvaluationRun:
        run = EvaluationRun(**kwargs)
        self.db.add(run)
        self.db.flush()
        return run

    def complete_run(
        self, run_id: int, metrics: dict, comparison: dict | None,
        degradation: list, improvement: list, samples: dict,
    ) -> EvaluationRun | None:
        run = self.db.get(EvaluationRun, run_id)
        if not run:
            return None
        run.status = "completed"
        run.metrics_json = metrics
        run.comparison_json = comparison
        run.degradation_flags = degradation
        run.improvement_flags = improvement
        run.sample_counts = samples
        run.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        return run

    def get_latest(self, tenant_id: str | None, window_label: str) -> EvaluationRun | None:
        q = self.db.query(EvaluationRun).filter(
            EvaluationRun.window_label == window_label,
            EvaluationRun.status == "completed",
        )
        if tenant_id:
            q = q.filter(EvaluationRun.tenant_id == tenant_id)
        return q.order_by(EvaluationRun.completed_at.desc()).first()

    def list_recent(self, tenant_id: str | None = None, limit: int = 20) -> list[EvaluationRun]:
        q = self.db.query(EvaluationRun)
        if tenant_id:
            q = q.filter(EvaluationRun.tenant_id == tenant_id)
        return q.order_by(EvaluationRun.created_at.desc()).limit(limit).all()

    def save_metric(self, **kwargs: Any) -> MetricSnapshot:
        snap = MetricSnapshot(**kwargs)
        self.db.add(snap)
        self.db.flush()
        return snap


class AdaptationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Profiles ──
    def get_active_profile(self, tenant_id: str | None) -> AdaptiveScoringProfile | None:
        q = self.db.query(AdaptiveScoringProfile).filter(
            AdaptiveScoringProfile.is_active == True,
        )
        if tenant_id:
            q = q.filter(AdaptiveScoringProfile.tenant_id == tenant_id)
        else:
            q = q.filter(AdaptiveScoringProfile.tenant_id.is_(None))
        return q.first()

    def create_profile(self, **kwargs: Any) -> AdaptiveScoringProfile:
        p = AdaptiveScoringProfile(**kwargs)
        self.db.add(p)
        self.db.flush()
        return p

    def save_version(self, **kwargs: Any) -> AdaptationVersion:
        v = AdaptationVersion(**kwargs)
        self.db.add(v)
        self.db.flush()
        return v

    def get_profile(self, profile_id: int) -> AdaptiveScoringProfile | None:
        return self.db.get(AdaptiveScoringProfile, profile_id)

    def list_profiles(self, tenant_id: str | None = None) -> list[AdaptiveScoringProfile]:
        q = self.db.query(AdaptiveScoringProfile)
        if tenant_id:
            q = q.filter(AdaptiveScoringProfile.tenant_id == tenant_id)
        return q.order_by(AdaptiveScoringProfile.created_at.desc()).all()

    # ── Proposals ──
    def create_proposal(self, **kwargs: Any) -> AdaptationProposal:
        p = AdaptationProposal(**kwargs)
        self.db.add(p)
        self.db.flush()
        return p

    def get_proposal(self, proposal_id: int) -> AdaptationProposal | None:
        return self.db.get(AdaptationProposal, proposal_id)

    def list_proposals(
        self, tenant_id: str | None = None, status: str | None = None, limit: int = 50
    ) -> list[AdaptationProposal]:
        q = self.db.query(AdaptationProposal)
        if tenant_id:
            q = q.filter(AdaptationProposal.tenant_id == tenant_id)
        if status:
            q = q.filter(AdaptationProposal.status == status)
        return q.order_by(AdaptationProposal.created_at.desc()).limit(limit).all()

    def count_pending(self, tenant_id: str | None = None) -> int:
        q = self.db.query(func.count(AdaptationProposal.id)).filter(
            AdaptationProposal.status == "pending"
        )
        if tenant_id:
            q = q.filter(AdaptationProposal.tenant_id == tenant_id)
        return q.scalar() or 0

    # ── Scoring Logs ──
    def log_scoring(self, **kwargs: Any) -> AdaptiveScoringLog:
        log = AdaptiveScoringLog(**kwargs)
        self.db.add(log)
        self.db.flush()
        return log

    # ── Rollbacks ──
    def create_rollback(self, **kwargs: Any) -> RollbackRecord:
        r = RollbackRecord(**kwargs)
        self.db.add(r)
        self.db.flush()
        return r

    def count_recent_rollbacks(self, days: int = 7) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            self.db.query(func.count(RollbackRecord.id))
            .filter(RollbackRecord.created_at >= since)
            .scalar() or 0
        )

    def get_version(self, profile_id: int, version: int) -> AdaptationVersion | None:
        return (
            self.db.query(AdaptationVersion)
            .filter(
                AdaptationVersion.profile_id == profile_id,
                AdaptationVersion.version == version,
            )
            .first()
        )


class GoalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs: Any) -> GoalDefinition:
        g = GoalDefinition(**kwargs)
        self.db.add(g)
        self.db.flush()
        return g

    def get(self, goal_id: int) -> GoalDefinition | None:
        return self.db.get(GoalDefinition, goal_id)

    def list_active(self, tenant_id: str | None = None) -> list[GoalDefinition]:
        q = self.db.query(GoalDefinition).filter(GoalDefinition.is_active == True)
        if tenant_id:
            q = q.filter(GoalDefinition.tenant_id == tenant_id)
        return q.order_by(GoalDefinition.priority).all()

    def list_all(self, tenant_id: str | None = None, limit: int = 50) -> list[GoalDefinition]:
        q = self.db.query(GoalDefinition)
        if tenant_id:
            q = q.filter(GoalDefinition.tenant_id == tenant_id)
        return q.order_by(GoalDefinition.created_at.desc()).limit(limit).all()

    def create_optimization_run(self, **kwargs: Any) -> OptimizationRun:
        r = OptimizationRun(**kwargs)
        self.db.add(r)
        self.db.flush()
        return r


class ExperimentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs: Any) -> AdaptationExperiment:
        e = AdaptationExperiment(**kwargs)
        self.db.add(e)
        self.db.flush()
        return e

    def get(self, exp_id: int) -> AdaptationExperiment | None:
        return self.db.get(AdaptationExperiment, exp_id)

    def list_all(
        self, tenant_id: str | None = None, status: str | None = None, limit: int = 50
    ) -> list[AdaptationExperiment]:
        q = self.db.query(AdaptationExperiment)
        if tenant_id:
            q = q.filter(AdaptationExperiment.tenant_id == tenant_id)
        if status:
            q = q.filter(AdaptationExperiment.status == status)
        return q.order_by(AdaptationExperiment.created_at.desc()).limit(limit).all()

    def count_active(self) -> int:
        return (
            self.db.query(func.count(AdaptationExperiment.id))
            .filter(AdaptationExperiment.status.in_(["pending", "running"]))
            .scalar() or 0
        )


class SourceLearningRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current(self, tenant_id: str | None, source_name: str, topic_key: str = "__global__") -> SourceTrustCurrent | None:
        return (
            self.db.query(SourceTrustCurrent)
            .filter(
                SourceTrustCurrent.tenant_id == tenant_id if tenant_id else SourceTrustCurrent.tenant_id.is_(None),
                SourceTrustCurrent.source_name == source_name,
                SourceTrustCurrent.topic_key == topic_key,
            )
            .first()
        )

    def upsert_current(
        self, tenant_id: str | None, source_name: str, topic_key: str = "__global__", **kwargs: Any
    ) -> SourceTrustCurrent:
        existing = self.get_current(tenant_id, source_name, topic_key)
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            self.db.flush()
            return existing
        rec = SourceTrustCurrent(
            tenant_id=tenant_id, source_name=source_name, topic_key=topic_key, **kwargs
        )
        self.db.add(rec)
        self.db.flush()
        return rec

    def list_by_tenant(self, tenant_id: str | None = None) -> list[SourceTrustCurrent]:
        q = self.db.query(SourceTrustCurrent)
        if tenant_id:
            q = q.filter(SourceTrustCurrent.tenant_id == tenant_id)
        return q.order_by(SourceTrustCurrent.trust_score.asc()).all()

    def save_history(self, **kwargs: Any) -> SourceTrustHistory:
        h = SourceTrustHistory(**kwargs)
        self.db.add(h)
        self.db.flush()
        return h

    def get_history(
        self, tenant_id: str | None, source_name: str, limit: int = 50
    ) -> list[SourceTrustHistory]:
        q = self.db.query(SourceTrustHistory).filter(
            SourceTrustHistory.source_name == source_name,
        )
        if tenant_id:
            q = q.filter(SourceTrustHistory.tenant_id == tenant_id)
        return q.order_by(SourceTrustHistory.measured_at.desc()).limit(limit).all()


class QualityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_report(self, **kwargs: Any) -> SelfEvaluationReport:
        r = SelfEvaluationReport(**kwargs)
        self.db.add(r)
        self.db.flush()
        return r

    def list_reports(
        self, tenant_id: str | None = None, report_type: str | None = None, limit: int = 20
    ) -> list[SelfEvaluationReport]:
        q = self.db.query(SelfEvaluationReport)
        if tenant_id:
            q = q.filter(SelfEvaluationReport.tenant_id == tenant_id)
        if report_type:
            q = q.filter(SelfEvaluationReport.report_type == report_type)
        return q.order_by(SelfEvaluationReport.created_at.desc()).limit(limit).all()
