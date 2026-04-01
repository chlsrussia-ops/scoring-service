"""Built-in workflow definitions."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.workflows.engine import WorkflowDefinition

logger = logging.getLogger("scoring_service")


# ── Step handlers ────────────────────────────────────────────────────

def step_run_evaluation(ctx: dict, config: dict, db: Session, settings: Settings) -> dict:
    """Run evaluation cycle."""
    from scoring_service.adaptation.evaluation_service import EvaluationService
    svc = EvaluationService(db, settings)
    window = config.get("window", "24h")
    result = svc.run_evaluation(ctx.get("tenant_id"), window)
    return {"evaluation": result}


def step_update_source_trust(ctx: dict, config: dict, db: Session, settings: Settings) -> dict:
    """Update source trust scores."""
    from scoring_service.adaptation.source_learning_service import SourceLearningService
    svc = SourceLearningService(db, settings)
    updates = svc.update_source_trust(ctx.get("tenant_id"))
    return {"source_updates": len(updates)}


def step_generate_proposals(ctx: dict, config: dict, db: Session, settings: Settings) -> dict:
    """Generate adaptation proposals."""
    from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
    svc = PolicyTuningService(db, settings)
    proposals = svc.generate_proposals(ctx.get("tenant_id"))
    return {"proposals_generated": len(proposals)}


def step_check_rollbacks(ctx: dict, config: dict, db: Session, settings: Settings) -> dict:
    """Check for degradation and auto-rollback."""
    from scoring_service.adaptation.rollback_service import RollbackService
    svc = RollbackService(db, settings)
    rollbacks = svc.auto_rollback_if_degraded(ctx.get("tenant_id"))
    return {"rollbacks": len(rollbacks)}


def step_evaluate_goals(ctx: dict, config: dict, db: Session, settings: Settings) -> dict:
    """Evaluate goal progress."""
    from scoring_service.adaptation.goal_service import GoalOptimizationService
    svc = GoalOptimizationService(db, settings)
    results = svc.evaluate_goals(ctx.get("tenant_id"))
    return {"goals_evaluated": len(results)}


def step_run_benchmark(ctx: dict, config: dict, db: Session, settings: Settings) -> dict:
    """Run benchmark evaluation."""
    from scoring_service.evaluation.service import EvaluationExecutionService
    svc = EvaluationExecutionService(db, settings)
    dataset_id = config.get("dataset_id") or ctx.get("dataset_id")
    if not dataset_id:
        return {"skipped": True, "reason": "no dataset_id"}
    result = svc.execute_run(
        dataset_id=dataset_id,
        strategy_name=config.get("strategy_name", "default"),
        strategy_version=config.get("strategy_version", "v1"),
        tenant_id=ctx.get("tenant_id"),
    )
    return {"benchmark_result": result}


def step_noop(ctx: dict, config: dict, db: Session, settings: Settings) -> dict:
    """No-op step for testing."""
    return {"noop": True}


# ── Register workflows ───────────────────────────────────────────────

def register_builtin_workflows() -> None:
    """Register all built-in workflow definitions."""

    WorkflowDefinition("adaptation_cycle", [
        ("evaluate", step_run_evaluation, True, 3),
        ("source_learning", step_update_source_trust, True, 3),
        ("generate_proposals", step_generate_proposals, True, 2),
        ("check_rollbacks", step_check_rollbacks, True, 2),
        ("evaluate_goals", step_evaluate_goals, True, 2),
    ]).register()

    WorkflowDefinition("benchmark_run", [
        ("run_benchmark", step_run_benchmark, True, 2),
    ]).register()

    WorkflowDefinition("source_reconciliation", [
        ("update_trust", step_update_source_trust, True, 3),
        ("generate_proposals", step_generate_proposals, True, 2),
    ]).register()

    WorkflowDefinition("full_maintenance", [
        ("evaluate", step_run_evaluation, True, 3),
        ("source_learning", step_update_source_trust, True, 3),
        ("generate_proposals", step_generate_proposals, True, 2),
        ("check_rollbacks", step_check_rollbacks, True, 2),
        ("evaluate_goals", step_evaluate_goals, True, 2),
    ]).register()

    WorkflowDefinition("test_workflow", [
        ("step1", step_noop, True, 3),
        ("step2", step_noop, True, 3),
    ]).register()

    logger.info("builtin_workflows_registered count=%d", len(["adaptation_cycle", "benchmark_run", "source_reconciliation", "full_maintenance", "test_workflow"]))
