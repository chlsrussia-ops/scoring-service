"""API routes for Stage 5: Adaptation & Self-Improving System."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from scoring_service.adaptation_contracts import (
    FeedbackCreate,
    FeedbackOut,
    GoalCreate,
    GoalOut,
    OutcomeCreate,
    OutcomeOut,
    ProposalAction,
    ProposalOut,
)
from scoring_service.config import Settings
from scoring_service.security import require_admin_key, require_api_key

# ── Public / App API ─────────────────────────────────────────────────

adaptation_router = APIRouter(prefix="/v1", tags=["adaptation"])


def _get_db(request: Request):
    factory = getattr(request.app.state, "session_factory", None)
    if not factory:
        raise HTTPException(503, "database unavailable")
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _tenant_id(request: Request) -> str:
    return request.query_params.get("tenant_id", request.app.state.settings.demo_tenant_id)


# ── Feedback ─────────────────────────────────────────────────────────

@adaptation_router.post("/feedback", status_code=201)
def create_feedback(
    body: FeedbackCreate, request: Request, db=Depends(_get_db),
):
    from scoring_service.adaptation.feedback_service import FeedbackService
    svc = FeedbackService(db, _settings(request))
    fb = svc.record_feedback(
        tenant_id=_tenant_id(request), target_type=body.target_type,
        target_id=body.target_id, feedback_type=body.feedback_type,
        label=body.label, score=body.score,
        usefulness_rating=body.usefulness_rating,
        confidence_rating=body.confidence_rating,
        reviewer=body.reviewer, source=body.source,
        evidence_snapshot=body.evidence_snapshot, metadata=body.metadata,
    )
    db.commit()
    return FeedbackOut.model_validate(fb).model_dump()


@adaptation_router.get("/feedback")
def list_feedback(
    request: Request, limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0), db=Depends(_get_db),
):
    from scoring_service.adaptation.feedback_service import FeedbackService
    svc = FeedbackService(db, _settings(request))
    items = svc.list_feedback(_tenant_id(request), limit, offset)
    return {"items": [FeedbackOut.model_validate(f).model_dump() for f in items], "count": len(items)}


# ── Outcomes ─────────────────────────────────────────────────────────

@adaptation_router.post("/outcomes", status_code=201)
def create_outcome(
    body: OutcomeCreate, request: Request, db=Depends(_get_db),
):
    from scoring_service.adaptation.feedback_service import FeedbackService
    svc = FeedbackService(db, _settings(request))
    rec = svc.record_outcome(
        tenant_id=_tenant_id(request), entity_type=body.entity_type,
        entity_id=body.entity_id, outcome_type=body.outcome_type,
        outcome_value=body.outcome_value,
        measurement_window_hours=body.measurement_window_hours,
        confidence=body.confidence, evidence=body.evidence,
    )
    db.commit()
    return OutcomeOut.model_validate(rec).model_dump()


# ── Evaluation ───────────────────────────────────────────────────────

@adaptation_router.get("/evaluation/summary")
def evaluation_summary(
    request: Request, window: str = Query("7d"),
    db=Depends(_get_db),
):
    from scoring_service.adaptation.evaluation_service import EvaluationService
    svc = EvaluationService(db, _settings(request))
    return svc.get_scorecard(_tenant_id(request), window)


@adaptation_router.get("/evaluation/scorecards")
def evaluation_scorecards(request: Request, db=Depends(_get_db)):
    from scoring_service.adaptation.evaluation_service import EvaluationService
    svc = EvaluationService(db, _settings(request))
    tid = _tenant_id(request)
    scorecards = []
    for w in _settings(request).evaluation_window_list:
        scorecards.append(svc.get_scorecard(tid, w))
    return {"scorecards": scorecards}


# ── Source Learning ──────────────────────────────────────────────────

@adaptation_router.get("/source-learning/summary")
def source_learning_summary(request: Request, db=Depends(_get_db)):
    from scoring_service.adaptation.source_learning_service import SourceLearningService
    svc = SourceLearningService(db, _settings(request))
    return svc.get_summary(_tenant_id(request))


# ── Goals ────────────────────────────────────────────────────────────

@adaptation_router.get("/goals")
def list_goals(request: Request, db=Depends(_get_db)):
    from scoring_service.adaptation.goal_service import GoalOptimizationService
    svc = GoalOptimizationService(db, _settings(request))
    goals = svc.list_goals(_tenant_id(request))
    return {"goals": [GoalOut.model_validate(g).model_dump() for g in goals]}


@adaptation_router.post("/goals", status_code=201)
def create_goal(body: GoalCreate, request: Request, db=Depends(_get_db)):
    from scoring_service.adaptation.goal_service import GoalOptimizationService
    svc = GoalOptimizationService(db, _settings(request))
    goal = svc.create_goal(
        tenant_id=_tenant_id(request), name=body.name,
        description=body.description, target_metric=body.target_metric,
        direction=body.direction, target_value=body.target_value,
        guardrails_json=body.guardrails, segment_type=body.segment_type,
        segment_value=body.segment_value, evaluation_window=body.evaluation_window,
        adaptation_strategy=body.adaptation_strategy,
        approval_mode=body.approval_mode, priority=body.priority,
    )
    db.commit()
    return GoalOut.model_validate(goal).model_dump()


# ── Experiments ──────────────────────────────────────────────────────

@adaptation_router.get("/experiments")
def list_experiments(
    request: Request, status: str | None = Query(None),
    db=Depends(_get_db),
):
    from scoring_service.adaptation.experiment_service import ExperimentService
    from scoring_service.adaptation_contracts import ExperimentOut
    svc = ExperimentService(db, _settings(request))
    exps = svc.list_experiments(_tenant_id(request), status)
    return {"experiments": [ExperimentOut.model_validate(e).model_dump() for e in exps]}


# ── Adaptation Status ────────────────────────────────────────────────

@adaptation_router.get("/adaptation/status")
def adaptation_status(request: Request, db=Depends(_get_db)):
    from scoring_service.adaptation.orchestrator import AdaptationOrchestrator
    orch = AdaptationOrchestrator(db, _settings(request))
    return orch.get_status(_tenant_id(request))


# ══ Admin API ════════════════════════════════════════════════════════

adaptation_admin_router = APIRouter(
    prefix="/v1/admin/adaptation",
    tags=["adaptation-admin"],
    dependencies=[Depends(require_admin_key)],
)


def _admin_get_db(request: Request):
    factory = getattr(request.app.state, "session_factory", None)
    if not factory:
        raise HTTPException(503, "database unavailable")
    db = factory()
    try:
        yield db
    finally:
        db.close()


# ── Proposals ────────────────────────────────────────────────────────

@adaptation_admin_router.get("/proposals")
def admin_list_proposals(
    request: Request, status: str | None = Query(None),
    tenant_id: str | None = Query(None),
    limit: int = Query(50, le=200), db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.repository import AdaptationRepository
    repo = AdaptationRepository(db)
    props = repo.list_proposals(tenant_id, status, limit)
    return {"proposals": [ProposalOut.model_validate(p).model_dump() for p in props]}


@adaptation_admin_router.get("/proposals/{proposal_id}")
def admin_get_proposal(
    proposal_id: int, request: Request, db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.repository import AdaptationRepository
    repo = AdaptationRepository(db)
    p = repo.get_proposal(proposal_id)
    if not p:
        raise HTTPException(404, "proposal not found")
    return ProposalOut.model_validate(p).model_dump()


@adaptation_admin_router.post("/proposals/{proposal_id}/approve")
def admin_approve_proposal(
    proposal_id: int, body: ProposalAction, request: Request, db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
    svc = PolicyTuningService(db, _settings(request))
    result = svc.approve_proposal(proposal_id, body.actor)
    db.commit()
    return result


@adaptation_admin_router.post("/proposals/{proposal_id}/reject")
def admin_reject_proposal(
    proposal_id: int, body: ProposalAction, request: Request, db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
    svc = PolicyTuningService(db, _settings(request))
    result = svc.reject_proposal(proposal_id, body.actor)
    db.commit()
    return result


@adaptation_admin_router.post("/proposals/{proposal_id}/apply")
def admin_apply_proposal(
    proposal_id: int, request: Request, db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
    svc = PolicyTuningService(db, _settings(request))
    result = svc.apply_proposal(proposal_id, actor="admin")
    db.commit()
    return result


@adaptation_admin_router.post("/proposals/{proposal_id}/simulate")
def admin_simulate_proposal(
    proposal_id: int, request: Request, db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
    svc = PolicyTuningService(db, _settings(request))
    return svc.simulate_proposal(proposal_id)


# ── Rollbacks ────────────────────────────────────────────────────────

@adaptation_admin_router.post("/rollbacks/{proposal_id}/execute")
def admin_rollback(
    proposal_id: int, request: Request, db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.rollback_service import RollbackService

    class RollbackBody(BaseModel):
        reason: str = "manual rollback"

    # Parse body if present
    reason = "manual rollback"
    svc = RollbackService(db, _settings(request))
    result = svc.rollback_proposal(proposal_id, reason, actor="admin")
    db.commit()
    return result


# ── Experiments ──────────────────────────────────────────────────────

@adaptation_admin_router.get("/experiments")
def admin_list_experiments(
    request: Request, status: str | None = Query(None),
    db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.experiment_service import ExperimentService
    from scoring_service.adaptation_contracts import ExperimentOut
    svc = ExperimentService(db, _settings(request))
    exps = svc.list_experiments(status=status)
    return {"experiments": [ExperimentOut.model_validate(e).model_dump() for e in exps]}


@adaptation_admin_router.post("/experiments/{experiment_id}/rollout")
def admin_run_experiment(
    experiment_id: int, request: Request, db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.experiment_service import ExperimentService
    svc = ExperimentService(db, _settings(request))
    result = svc.run_replay(experiment_id)
    db.commit()
    return result


# ── Scorecards ───────────────────────────────────────────────────────

@adaptation_admin_router.get("/scorecards")
def admin_scorecards(request: Request, db=Depends(_admin_get_db)):
    from scoring_service.adaptation.evaluation_service import EvaluationService
    svc = EvaluationService(db, _settings(request))
    scorecards = []
    for w in _settings(request).evaluation_window_list:
        scorecards.append(svc.get_scorecard(None, w))
    return {"scorecards": scorecards}


# ── Evaluations ──────────────────────────────────────────────────────

@adaptation_admin_router.get("/evaluations")
def admin_list_evaluations(
    request: Request, limit: int = Query(20, le=100),
    db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.evaluation_service import EvaluationService
    svc = EvaluationService(db, _settings(request))
    return {"evaluations": svc.list_evaluations(limit=limit)}


# ── Source Trust ─────────────────────────────────────────────────────

@adaptation_admin_router.get("/source-trust")
def admin_source_trust(request: Request, db=Depends(_admin_get_db)):
    from scoring_service.adaptation.source_learning_service import SourceLearningService
    svc = SourceLearningService(db, _settings(request))
    return svc.get_summary()


# ── Goal Performance ─────────────────────────────────────────────────

@adaptation_admin_router.get("/goal-performance")
def admin_goal_performance(request: Request, db=Depends(_admin_get_db)):
    from scoring_service.adaptation.goal_service import GoalOptimizationService
    svc = GoalOptimizationService(db, _settings(request))
    return {"goals": svc.evaluate_goals()}


# ── Full Cycle (manual trigger) ──────────────────────────────────────

@adaptation_admin_router.post("/run-cycle")
def admin_run_cycle(
    request: Request, tenant_id: str | None = Query(None),
    db=Depends(_admin_get_db),
):
    from scoring_service.adaptation.orchestrator import AdaptationOrchestrator
    orch = AdaptationOrchestrator(db, _settings(request))
    return orch.run_full_cycle(tenant_id)
