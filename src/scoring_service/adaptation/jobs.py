"""Adaptation job handlers — registered with the worker job queue."""
from __future__ import annotations

import logging
from typing import Any

from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


def handle_adaptation_cycle(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Run full adaptation cycle for a tenant."""
    from scoring_service.db.session import create_session_factory
    _, session_factory = create_session_factory(settings)
    db = session_factory()
    try:
        from scoring_service.adaptation.orchestrator import AdaptationOrchestrator
        orch = AdaptationOrchestrator(db, settings)
        result = orch.run_full_cycle(payload.get("tenant_id"))
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        logger.exception("adaptation_cycle_job_failed")
        return {"error": str(exc)[:500]}
    finally:
        db.close()


def handle_evaluation_run(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Run evaluation for a specific window."""
    from scoring_service.db.session import create_session_factory
    _, session_factory = create_session_factory(settings)
    db = session_factory()
    try:
        from scoring_service.adaptation.evaluation_service import EvaluationService
        svc = EvaluationService(db, settings)
        result = svc.run_evaluation(
            tenant_id=payload.get("tenant_id"),
            window_label=payload.get("window", "24h"),
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)[:500]}
    finally:
        db.close()


def handle_source_learning(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Update source trust scores."""
    from scoring_service.db.session import create_session_factory
    _, session_factory = create_session_factory(settings)
    db = session_factory()
    try:
        from scoring_service.adaptation.source_learning_service import SourceLearningService
        svc = SourceLearningService(db, settings)
        updates = svc.update_source_trust(payload.get("tenant_id"))
        db.commit()
        return {"updates": len(updates)}
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)[:500]}
    finally:
        db.close()


def handle_proposal_generation(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Generate adaptation proposals."""
    from scoring_service.db.session import create_session_factory
    _, session_factory = create_session_factory(settings)
    db = session_factory()
    try:
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
        svc = PolicyTuningService(db, settings)
        proposals = svc.generate_proposals(payload.get("tenant_id"))
        db.commit()
        return {"proposals_generated": len(proposals)}
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)[:500]}
    finally:
        db.close()


def handle_rollback_monitor(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Check for degradation and auto-rollback if needed."""
    from scoring_service.db.session import create_session_factory
    _, session_factory = create_session_factory(settings)
    db = session_factory()
    try:
        from scoring_service.adaptation.rollback_service import RollbackService
        svc = RollbackService(db, settings)
        rollbacks = svc.auto_rollback_if_degraded(payload.get("tenant_id"))
        db.commit()
        return {"rollbacks": len(rollbacks)}
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)[:500]}
    finally:
        db.close()


def handle_goal_optimization(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Evaluate goals and generate optimization suggestions."""
    from scoring_service.db.session import create_session_factory
    _, session_factory = create_session_factory(settings)
    db = session_factory()
    try:
        from scoring_service.adaptation.goal_service import GoalOptimizationService
        svc = GoalOptimizationService(db, settings)
        results = svc.evaluate_goals(payload.get("tenant_id"))
        db.commit()
        return {"goals_evaluated": len(results)}
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)[:500]}
    finally:
        db.close()


# Registry for worker integration
ADAPTATION_JOB_HANDLERS = {
    "adaptation.full_cycle": handle_adaptation_cycle,
    "adaptation.evaluation": handle_evaluation_run,
    "adaptation.source_learning": handle_source_learning,
    "adaptation.proposals": handle_proposal_generation,
    "adaptation.rollback_monitor": handle_rollback_monitor,
    "adaptation.goal_optimization": handle_goal_optimization,
}
