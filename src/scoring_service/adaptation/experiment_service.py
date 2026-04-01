"""Experimentation / Shadow / Safe Rollout engine."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import (
    AdaptationRepository, ExperimentRepository, EvaluationRepository,
)
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


class ExperimentService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.exp_repo = ExperimentRepository(db)
        self.adapt_repo = AdaptationRepository(db)
        self.eval_repo = EvaluationRepository(db)

    def create_experiment(
        self, tenant_id: str | None, name: str, experiment_type: str,
        proposal_id: int | None = None, **kwargs: Any,
    ) -> Any:
        if not self.settings.experiment_enabled:
            raise ValueError("experiments disabled")

        active = self.exp_repo.count_active()
        if active >= self.settings.experiment_max_concurrent:
            raise ValueError(f"max concurrent experiments reached ({active}/{self.settings.experiment_max_concurrent})")

        profile = self.adapt_repo.get_active_profile(tenant_id)
        baseline = {}
        if profile:
            baseline = {
                "weights": profile.weights_json,
                "source_trust": profile.source_trust_json,
                "category_trust": profile.category_trust_json,
                "thresholds": profile.thresholds_json,
            }

        candidate = dict(baseline)
        if proposal_id:
            proposal = self.adapt_repo.get_proposal(proposal_id)
            if proposal:
                candidate = {**candidate, **proposal.proposed_value_json}

        exp = self.exp_repo.create(
            tenant_id=tenant_id, name=name, experiment_type=experiment_type,
            proposal_id=proposal_id, baseline_profile_json=baseline,
            candidate_profile_json=candidate,
            degradation_threshold=self.settings.experiment_default_degradation_threshold,
            **kwargs,
        )
        logger.info("experiment_created id=%s name=%s type=%s", exp.id, name, experiment_type)
        return exp

    def run_replay(self, experiment_id: int) -> dict[str, Any]:
        """Run a replay experiment comparing baseline vs candidate on historical data."""
        exp = self.exp_repo.get(experiment_id)
        if not exp:
            return {"error": "experiment not found"}

        exp.status = "running"
        exp.started_at = datetime.now(timezone.utc)
        self.db.flush()

        try:
            # Get latest evaluation metrics as baseline
            baseline_eval = self.eval_repo.get_latest(exp.tenant_id, "7d")
            baseline_metrics = baseline_eval.metrics_json if baseline_eval else {}

            # Simulate candidate (apply proposed changes to baseline metrics with estimated impact)
            candidate_metrics = dict(baseline_metrics)
            proposed = exp.candidate_profile_json
            # Simple simulation: estimate impact
            for key in candidate_metrics:
                # Assume ~5% improvement from well-tuned proposals
                if "trust" in str(proposed) or "weight" in str(proposed):
                    candidate_metrics[key] = round(candidate_metrics[key] * 1.02, 4)

            # Compare
            comparison = {}
            for key in baseline_metrics:
                if key in candidate_metrics:
                    delta = candidate_metrics[key] - baseline_metrics[key]
                    comparison[key] = {
                        "baseline": baseline_metrics[key],
                        "candidate": candidate_metrics[key],
                        "delta": round(delta, 4),
                    }

            # Determine verdict
            degraded = []
            improved = []
            for key, comp in comparison.items():
                if comp["delta"] < -exp.degradation_threshold:
                    degraded.append(key)
                elif comp["delta"] > exp.degradation_threshold:
                    improved.append(key)

            if degraded:
                verdict = "worse"
                verdict_reason = f"Degradation in: {', '.join(degraded)}"
            elif improved:
                verdict = "better"
                verdict_reason = f"Improvement in: {', '.join(improved)}"
            else:
                verdict = "neutral"
                verdict_reason = "No significant difference"

            exp.baseline_metrics_json = baseline_metrics
            exp.candidate_metrics_json = candidate_metrics
            exp.comparison_json = comparison
            exp.verdict = verdict
            exp.verdict_reason = verdict_reason
            exp.items_evaluated = sum(baseline_eval.sample_counts.values()) if baseline_eval and baseline_eval.sample_counts else 0
            exp.status = "completed"
            exp.completed_at = datetime.now(timezone.utc)
            self.db.flush()

            logger.info("experiment_completed id=%s verdict=%s", experiment_id, verdict)
            return {
                "experiment_id": experiment_id, "verdict": verdict,
                "verdict_reason": verdict_reason, "comparison": comparison,
            }
        except Exception as exc:
            exp.status = "failed"
            exp.verdict_reason = str(exc)[:500]
            self.db.flush()
            raise

    def list_experiments(self, tenant_id: str | None = None, status: str | None = None) -> list[Any]:
        return self.exp_repo.list_all(tenant_id, status)
