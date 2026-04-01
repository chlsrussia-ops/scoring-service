"""API routes for workflow orchestration."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from scoring_service.config import Settings
from scoring_service.security import require_admin_key

workflow_router = APIRouter(prefix="/v1/workflows", tags=["workflows"])
workflow_admin_router = APIRouter(prefix="/v1/admin/workflows", tags=["workflows-admin"], dependencies=[Depends(require_admin_key)])


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


def _tenant(request: Request) -> str | None:
    return request.query_params.get("tenant_id")


class WorkflowStartRequest(BaseModel):
    workflow_type: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    execute: bool = True


class ScheduleCreate(BaseModel):
    name: str
    workflow_type: str
    interval_seconds: int | None = None
    cron_expression: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


# ── Workflow runs ────────────────────────────────────────────────────

@workflow_router.post("/start", status_code=201)
def start_workflow(body: WorkflowStartRequest, request: Request, db=Depends(_get_db)):
    from scoring_service.workflows.engine import WorkflowEngine
    engine = WorkflowEngine(db, _settings(request))
    result = engine.start_workflow(
        workflow_type=body.workflow_type, input_data=body.input_data,
        tenant_id=_tenant(request), config=body.config,
        idempotency_key=body.idempotency_key,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    if body.execute and result.get("workflow_run_id") and not result.get("idempotent"):
        db.commit()
        exec_result = engine.execute_workflow(result["workflow_run_id"])
        return exec_result
    db.commit()
    return result


@workflow_router.get("/runs")
def list_runs(
    request: Request, status: str | None = Query(None),
    workflow_type: str | None = Query(None),
    limit: int = Query(50, le=200), db=Depends(_get_db),
):
    from scoring_service.workflows.engine import WorkflowEngine
    engine = WorkflowEngine(db, _settings(request))
    return {"runs": engine.list_runs(_tenant(request), status, workflow_type, limit)}


@workflow_router.get("/runs/{run_id}")
def get_run_status(run_id: int, request: Request, db=Depends(_get_db)):
    from scoring_service.workflows.engine import WorkflowEngine
    engine = WorkflowEngine(db, _settings(request))
    return engine.get_status(run_id)


@workflow_router.get("/types")
def list_types(request: Request):
    from scoring_service.workflows.engine import list_workflow_types
    return {"types": list_workflow_types()}


# ── Admin ────────────────────────────────────────────────────────────

@workflow_admin_router.post("/runs/{run_id}/retry")
def retry_workflow(run_id: int, request: Request, db=Depends(_get_db)):
    from scoring_service.workflows.engine import WorkflowEngine
    engine = WorkflowEngine(db, _settings(request))
    return engine.retry_workflow(run_id)


@workflow_admin_router.post("/runs/{run_id}/cancel")
def cancel_workflow(run_id: int, request: Request, db=Depends(_get_db)):
    from scoring_service.workflows.engine import WorkflowEngine
    engine = WorkflowEngine(db, _settings(request))
    return engine.cancel_workflow(run_id)


# ── Schedules ────────────────────────────────────────────────────────

@workflow_admin_router.get("/schedules")
def list_schedules(request: Request, db=Depends(_get_db)):
    from scoring_service.workflows.scheduler import WorkflowScheduler
    sched = WorkflowScheduler(db, _settings(request))
    return {"schedules": sched.list_schedules(_tenant(request))}


@workflow_admin_router.post("/schedules", status_code=201)
def create_schedule(body: ScheduleCreate, request: Request, db=Depends(_get_db)):
    from scoring_service.workflows.scheduler import WorkflowScheduler
    sched = WorkflowScheduler(db, _settings(request))
    result = sched.create_schedule(
        name=body.name, workflow_type=body.workflow_type,
        interval_seconds=body.interval_seconds,
        cron_expression=body.cron_expression,
        tenant_id=_tenant(request), config=body.config,
    )
    if "error" in result:
        raise HTTPException(409, result["error"])
    return result


@workflow_admin_router.post("/schedules/{schedule_id}/toggle")
def toggle_schedule(
    schedule_id: int, active: bool = Query(True),
    request: Request = None, db=Depends(_get_db),
):
    from scoring_service.workflows.scheduler import WorkflowScheduler
    sched = WorkflowScheduler(db, _settings(request))
    return sched.toggle_schedule(schedule_id, active)


@workflow_admin_router.post("/scheduler/tick")
def manual_tick(request: Request, db=Depends(_get_db)):
    from scoring_service.workflows.scheduler import WorkflowScheduler
    sched = WorkflowScheduler(db, _settings(request))
    return {"results": sched.tick()}
