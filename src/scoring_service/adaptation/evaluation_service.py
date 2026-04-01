"""Evaluation & Quality Metrics Engine — computes quality scorecards from feedback/outcomes."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import (
    EvaluationRepository, FeedbackRepository, OutcomeRepository, QualityRepository,
)
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")

WINDOW_MAP = {"24h": 1, "7d": 7, "30d": 30}


class EvaluationService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.eval_repo = EvaluationRepository(db)
        self.feedback_repo = FeedbackRepository(db)
        self.outcome_repo = OutcomeRepository(db)
        self.quality_repo = QualityRepository(db)

    def run_evaluation(self, tenant_id: str | None = None, window_label: str = "24h") -> dict[str, Any]:
        """Run a full evaluation cycle for a given window."""
        days = WINDOW_MAP.get(window_label, 1)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=days)

        run = self.eval_repo.create_run(
            tenant_id=tenant_id, window_start=window_start, window_end=now,
            window_label=window_label, status="running",
        )
        self.db.flush()

        try:
            metrics = self._compute_metrics(tenant_id, window_start, now)
            samples = self._compute_sample_counts(tenant_id, window_start)

            # Compare with previous
            previous = self.eval_repo.get_latest(tenant_id, window_label)
            comparison = None
            degradation_flags = []
            improvement_flags = []
            if previous and previous.metrics_json:
                comparison = {}
                for key, val in metrics.items():
                    prev_val = previous.metrics_json.get(key)
                    if prev_val is not None and isinstance(prev_val, (int, float)):
                        delta = val - prev_val
                        comparison[key] = {"current": val, "previous": prev_val, "delta": round(delta, 4)}
                        # Check degradation (lower is worse for precision-like metrics)
                        if key in self.settings.protected_metric_list:
                            if delta < -self.settings.adaptation_degradation_threshold:
                                degradation_flags.append(f"{key}: {prev_val:.3f} -> {val:.3f}")
                            elif delta > self.settings.adaptation_degradation_threshold:
                                improvement_flags.append(f"{key}: {prev_val:.3f} -> {val:.3f}")

            # Save metric snapshots
            for name, value in metrics.items():
                prev_val = previous.metrics_json.get(name) if previous and previous.metrics_json else None
                self.eval_repo.save_metric(
                    evaluation_run_id=run.id, metric_name=name,
                    metric_value=value, sample_count=samples.get(name, 0),
                    previous_value=prev_val,
                    delta=round(value - prev_val, 4) if prev_val is not None else None,
                    is_degraded=f"{name}:" in " ".join(degradation_flags),
                    is_improved=f"{name}:" in " ".join(improvement_flags),
                )

            self.eval_repo.complete_run(
                run.id, metrics, comparison, degradation_flags, improvement_flags, samples,
            )
            self.db.commit()

            logger.info(
                "evaluation_completed run_id=%s tenant=%s window=%s metrics=%d degraded=%d improved=%d",
                run.id, tenant_id, window_label, len(metrics), len(degradation_flags), len(improvement_flags),
            )
            return {
                "evaluation_run_id": run.id, "metrics": metrics,
                "degradation_flags": degradation_flags, "improvement_flags": improvement_flags,
                "sample_counts": samples,
            }
        except Exception as exc:
            run.status = "failed"
            self.db.commit()
            logger.exception("evaluation_failed run_id=%s error=%s", run.id, str(exc)[:300])
            raise

    def _compute_metrics(self, tenant_id: str | None, start: datetime, end: datetime) -> dict[str, float]:
        """Compute quality metrics from feedback and outcomes."""
        metrics: dict[str, float] = {}
        tid = tenant_id or "demo"

        # Alert metrics
        alert_outcomes = self.outcome_repo.count_by_type(tid, "alert", start)
        total_alerts = sum(alert_outcomes.values())
        if total_alerts >= self.settings.evaluation_min_sample_threshold:
            tp = alert_outcomes.get("true_positive", 0) + alert_outcomes.get("confirmed", 0) + alert_outcomes.get("acted_on", 0)
            fp = alert_outcomes.get("false_positive", 0) + alert_outcomes.get("rejected", 0)
            metrics["alert_precision"] = round(tp / max(tp + fp, 1), 4)
            metrics["alert_acceptance_rate"] = round(
                (total_alerts - alert_outcomes.get("ignored", 0)) / max(total_alerts, 1), 4
            )
            metrics["false_positive_rate"] = round(fp / max(total_alerts, 1), 4)

        # Recommendation metrics
        rec_feedback = self.feedback_repo.count_by_label(tid, "recommendation", start)
        total_rec = sum(rec_feedback.values())
        if total_rec >= self.settings.evaluation_min_sample_threshold:
            useful = rec_feedback.get("useful", 0) + rec_feedback.get("relevant", 0)
            metrics["recommendation_usefulness"] = round(useful / max(total_rec, 1), 4)

        # Trend metrics
        trend_outcomes = self.outcome_repo.count_by_type(tid, "trend", start)
        total_trends = sum(trend_outcomes.values())
        if total_trends >= self.settings.evaluation_min_sample_threshold:
            confirmed = trend_outcomes.get("confirmed", 0) + trend_outcomes.get("acted_on", 0)
            metrics["trend_confirmation_rate"] = round(confirmed / max(total_trends, 1), 4)
            noise = trend_outcomes.get("rejected", 0) + trend_outcomes.get("expired", 0)
            metrics["noise_rate"] = round(noise / max(total_trends, 1), 4)

        # Source quality average
        from scoring_service.adaptation.repository import SourceLearningRepository
        src_repo = SourceLearningRepository(self.db)
        sources = src_repo.list_by_tenant(tenant_id)
        if sources:
            avg_trust = sum(s.trust_score for s in sources) / len(sources)
            metrics["source_quality_avg"] = round(avg_trust, 4)

        return metrics

    def _compute_sample_counts(self, tenant_id: str | None, start: datetime) -> dict[str, int]:
        tid = tenant_id or "demo"
        counts: dict[str, int] = {}
        for entity_type in ["alert", "recommendation", "trend", "source"]:
            outcomes = self.outcome_repo.count_by_type(tid, entity_type, start)
            counts[f"{entity_type}_outcomes"] = sum(outcomes.values())
            feedback = self.feedback_repo.count_by_label(tid, entity_type, start)
            counts[f"{entity_type}_feedback"] = sum(feedback.values())
        return counts

    def get_scorecard(self, tenant_id: str | None = None, window: str = "7d") -> dict[str, Any]:
        """Get the latest scorecard for a tenant."""
        run = self.eval_repo.get_latest(tenant_id, window)
        if not run:
            return {"tenant_id": tenant_id, "window": window, "message": "no evaluation data"}
        return {
            "tenant_id": tenant_id, "window": window,
            "evaluation_run_id": run.id,
            "metrics": run.metrics_json,
            "degradation_flags": run.degradation_flags,
            "improvement_flags": run.improvement_flags,
            "sample_counts": run.sample_counts,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }

    def list_evaluations(self, tenant_id: str | None = None, limit: int = 20) -> list[dict]:
        runs = self.eval_repo.list_recent(tenant_id, limit)
        return [
            {
                "id": r.id, "tenant_id": r.tenant_id, "window_label": r.window_label,
                "status": r.status, "metrics": r.metrics_json,
                "degradation_flags": r.degradation_flags,
                "improvement_flags": r.improvement_flags,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ]
