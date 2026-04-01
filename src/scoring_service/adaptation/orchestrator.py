"""Adaptation Orchestrator — coordinates the self-improvement loop."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.evaluation_service import EvaluationService
from scoring_service.adaptation.experiment_service import ExperimentService
from scoring_service.adaptation.goal_service import GoalOptimizationService
from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
from scoring_service.adaptation.repository import (
    AdaptationRepository, ExperimentRepository, GoalRepository, QualityRepository,
)
from scoring_service.adaptation.rollback_service import RollbackService
from scoring_service.adaptation.source_learning_service import SourceLearningService
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


class AdaptationOrchestrator:
    """Main orchestrator for the self-improvement loop:
    observe → evaluate → learn → propose → validate → apply → monitor → rollback
    """

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.evaluation = EvaluationService(db, settings)
        self.source_learning = SourceLearningService(db, settings)
        self.policy_tuning = PolicyTuningService(db, settings)
        self.goal_optimization = GoalOptimizationService(db, settings)
        self.experiment = ExperimentService(db, settings)
        self.rollback = RollbackService(db, settings)
        self.adapt_repo = AdaptationRepository(db)
        self.exp_repo = ExperimentRepository(db)
        self.goal_repo = GoalRepository(db)
        self.quality_repo = QualityRepository(db)

    def run_full_cycle(self, tenant_id: str | None = None) -> dict[str, Any]:
        """Execute the full adaptation cycle."""
        results: dict[str, Any] = {"tenant_id": tenant_id, "steps": {}}

        if not self.settings.adaptation_enabled:
            results["status"] = "disabled"
            return results

        try:
            # Step 1: Evaluate
            eval_results = {}
            for window in self.settings.evaluation_window_list:
                eval_results[window] = self.evaluation.run_evaluation(tenant_id, window)
            results["steps"]["evaluation"] = {
                "windows": list(eval_results.keys()),
                "metrics_count": sum(len(r.get("metrics", {})) for r in eval_results.values()),
            }

            # Step 2: Source learning
            source_updates = self.source_learning.update_source_trust(tenant_id)
            results["steps"]["source_learning"] = {"updates": len(source_updates)}

            # Step 3: Generate proposals
            proposals = self.policy_tuning.generate_proposals(tenant_id)
            results["steps"]["proposals"] = {"generated": len(proposals)}

            # Step 4: Auto-apply safe proposals if mode allows
            auto_applied = 0
            if self.settings.adaptation_mode in ("auto_safe", "auto_safe_with_audit"):
                for p in proposals:
                    pid = p.get("proposal_id")
                    if pid:
                        proposal = self.adapt_repo.get_proposal(pid)
                        if proposal and proposal.risk_level == "safe":
                            result = self.policy_tuning.apply_proposal(pid, actor="auto")
                            if "error" not in result:
                                auto_applied += 1
            results["steps"]["auto_applied"] = auto_applied

            # Step 5: Goal optimization
            goal_results = self.goal_optimization.evaluate_goals(tenant_id)
            results["steps"]["goals"] = {"evaluated": len(goal_results)}

            # Step 6: Check for rollbacks needed
            rollbacks = self.rollback.auto_rollback_if_degraded(tenant_id)
            results["steps"]["rollbacks"] = {"executed": len(rollbacks)}

            # Step 7: Self-evaluation report
            self.quality_repo.save_report(
                tenant_id=tenant_id, report_type="quality",
                summary=f"Adaptation cycle completed: {len(proposals)} proposals, {auto_applied} auto-applied, {len(rollbacks)} rollbacks",
                details_json=results,
            )

            results["status"] = "completed"
            self.db.commit()

        except Exception as exc:
            results["status"] = "failed"
            results["error"] = str(exc)[:500]
            logger.exception("adaptation_cycle_failed tenant=%s", tenant_id)
            self.db.rollback()

        logger.info(
            "adaptation_cycle tenant=%s status=%s proposals=%d auto_applied=%d",
            tenant_id, results["status"],
            results.get("steps", {}).get("proposals", {}).get("generated", 0),
            results.get("steps", {}).get("auto_applied", 0),
        )
        return results

    def get_status(self, tenant_id: str | None = None) -> dict[str, Any]:
        """Get current adaptation system status."""
        from scoring_service.adaptation.repository import EvaluationRepository
        eval_repo = EvaluationRepository(self.db)

        pending = self.adapt_repo.count_pending(tenant_id)
        active_exp = self.exp_repo.count_active()
        goals = self.goal_repo.list_active(tenant_id)
        recent_evals = eval_repo.list_recent(tenant_id, limit=5)
        recent_rollbacks = self.adapt_repo.count_recent_rollbacks()

        last_eval = recent_evals[0] if recent_evals else None
        degraded = last_eval.degradation_flags if last_eval else []
        improvements = last_eval.improvement_flags if last_eval else []

        return {
            "mode": self.settings.adaptation_mode,
            "enabled": self.settings.adaptation_enabled,
            "pending_proposals": pending,
            "active_experiments": active_exp,
            "active_goals": len(goals),
            "recent_evaluations": len(recent_evals),
            "recent_rollbacks": recent_rollbacks,
            "last_evaluation_at": last_eval.completed_at.isoformat() if last_eval and last_eval.completed_at else None,
            "degraded_metrics": degraded,
            "improvements": improvements,
        }
