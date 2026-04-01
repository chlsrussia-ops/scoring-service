"""Goal-Driven Optimization — optimizes system toward defined objectives."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import (
    AdaptationRepository, EvaluationRepository, GoalRepository,
)
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


class GoalOptimizationService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.goal_repo = GoalRepository(db)
        self.eval_repo = EvaluationRepository(db)
        self.adapt_repo = AdaptationRepository(db)

    def create_goal(self, tenant_id: str | None, **kwargs: Any) -> Any:
        return self.goal_repo.create(tenant_id=tenant_id, **kwargs)

    def list_goals(self, tenant_id: str | None = None) -> list[Any]:
        return self.goal_repo.list_all(tenant_id)

    def evaluate_goals(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Evaluate progress against all active goals."""
        if not self.settings.goal_optimization_enabled:
            return []

        goals = self.goal_repo.list_active(tenant_id)
        results = []
        for goal in goals:
            result = self._evaluate_single_goal(goal)
            results.append(result)
        return results

    def _evaluate_single_goal(self, goal) -> dict[str, Any]:
        """Evaluate a single goal's progress."""
        run = self.eval_repo.get_latest(goal.tenant_id, goal.evaluation_window)
        current_value = None
        if run and run.metrics_json:
            current_value = run.metrics_json.get(goal.target_metric)

        progress_pct = None
        status = "unknown"
        if current_value is not None and goal.target_value is not None:
            if goal.direction == "maximize":
                progress_pct = (current_value / goal.target_value * 100) if goal.target_value > 0 else 0
                status = "achieved" if current_value >= goal.target_value else (
                    "on_track" if progress_pct >= 70 else "at_risk" if progress_pct >= 40 else "off_track"
                )
            else:
                # minimize: lower is better
                if goal.target_value > 0:
                    progress_pct = ((1 - current_value / goal.target_value) * 100 + 100)
                status = "achieved" if current_value <= goal.target_value else (
                    "on_track" if current_value <= goal.target_value * 1.3 else "off_track"
                )
        elif current_value is not None:
            status = "tracking"

        # Check guardrail violations
        violations = []
        if run and run.metrics_json and goal.guardrails_json:
            for metric, bounds in goal.guardrails_json.items():
                val = run.metrics_json.get(metric)
                if val is not None:
                    if "min" in bounds and val < bounds["min"]:
                        violations.append(f"{metric} ({val:.3f}) below min ({bounds['min']})")
                    if "max" in bounds and val > bounds["max"]:
                        violations.append(f"{metric} ({val:.3f}) above max ({bounds['max']})")

        # Save optimization run
        opt_run = self.goal_repo.create_optimization_run(
            goal_id=goal.id, tenant_id=goal.tenant_id,
            status="completed", current_value=current_value,
            target_value=goal.target_value, progress_pct=progress_pct,
            guardrail_violations=violations,
        )
        self.db.flush()

        return {
            "goal_id": goal.id, "goal_name": goal.name,
            "target_metric": goal.target_metric, "direction": goal.direction,
            "current_value": current_value, "target_value": goal.target_value,
            "progress_pct": round(progress_pct, 1) if progress_pct else None,
            "status": status, "guardrail_violations": violations,
            "optimization_run_id": opt_run.id,
        }
