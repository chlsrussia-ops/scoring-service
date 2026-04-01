"""API routes for Ranking Evaluation Framework."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from scoring_service.config import Settings
from scoring_service.security import require_admin_key


eval_router = APIRouter(prefix="/v1/eval", tags=["evaluation"])


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


def _tenant_id(request: Request) -> str | None:
    return request.query_params.get("tenant_id")


# ── Pydantic ─────────────────────────────────────────────────────────

class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    benchmark_type: str = Field(default="ranking")
    description: str | None = None
    version: int = 1
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ItemImport(BaseModel):
    items: list[dict[str, Any]]


class RunRequest(BaseModel):
    dataset_id: int
    strategy_name: str
    strategy_version: str = "v1"
    config: dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    baseline_run_id: int
    candidate_run_id: int


class GuardrailCreate(BaseModel):
    metric_name: str
    min_value: float | None = None
    max_regression_delta: float | None = None
    segment_category: str | None = None
    segment_value: str | None = None
    severity: str = Field(default="error")


# ── Benchmark Datasets ───────────────────────────────────────────────

@eval_router.post("/datasets", status_code=201)
def create_dataset(body: DatasetCreate, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import BenchmarkService
    svc = BenchmarkService(db, _settings(request))
    ds = svc.create_dataset(
        tenant_id=_tenant_id(request), name=body.name,
        benchmark_type=body.benchmark_type, description=body.description,
        version=body.version, tags=body.tags, metadata=body.metadata,
    )
    db.commit()
    return {"id": ds.id, "name": ds.name, "version": ds.version, "type": ds.benchmark_type}


@eval_router.get("/datasets")
def list_datasets(request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import BenchmarkService
    svc = BenchmarkService(db, _settings(request))
    datasets = svc.list_datasets(_tenant_id(request))
    return {
        "datasets": [
            {"id": d.id, "name": d.name, "version": d.version, "type": d.benchmark_type,
             "items": d.item_count, "frozen": d.is_frozen, "tags": d.tags}
            for d in datasets
        ]
    }


@eval_router.post("/datasets/{dataset_id}/import", status_code=201)
def import_items(dataset_id: int, body: ItemImport, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import BenchmarkService
    svc = BenchmarkService(db, _settings(request))
    return svc.import_items(dataset_id, body.items)


@eval_router.post("/datasets/{dataset_id}/freeze")
def freeze_dataset(dataset_id: int, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import BenchmarkService
    svc = BenchmarkService(db, _settings(request))
    ds = svc.freeze(dataset_id)
    db.commit()
    if not ds:
        raise HTTPException(404, "dataset not found")
    return {"id": ds.id, "frozen": ds.is_frozen}


@eval_router.get("/datasets/{dataset_id}/segments")
def dataset_segments(dataset_id: int, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import BenchmarkService
    svc = BenchmarkService(db, _settings(request))
    return {"segments": svc.get_segments(dataset_id)}


# ── Evaluation Runs ──────────────────────────────────────────────────

@eval_router.post("/runs", status_code=201)
def start_run(body: RunRequest, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import EvaluationExecutionService
    svc = EvaluationExecutionService(db, _settings(request))
    return svc.execute_run(
        dataset_id=body.dataset_id, strategy_name=body.strategy_name,
        strategy_version=body.strategy_version, tenant_id=_tenant_id(request),
        config=body.config,
    )


@eval_router.get("/runs")
def list_runs(
    request: Request, dataset_id: int | None = Query(None),
    db=Depends(_get_db),
):
    from scoring_service.evaluation.repository import EvalRunRepository
    repo = EvalRunRepository(db)
    runs = repo.list_runs(dataset_id, _tenant_id(request))
    return {
        "runs": [
            {"id": r.id, "dataset_id": r.dataset_id, "strategy": r.strategy_name,
             "version": r.strategy_version, "status": r.status, "items": r.item_count,
             "duration_ms": r.duration_ms, "created_at": r.created_at.isoformat()}
            for r in runs
        ]
    }


@eval_router.get("/runs/{run_id}")
def get_run_result(run_id: int, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import EvaluationExecutionService
    svc = EvaluationExecutionService(db, _settings(request))
    return svc.get_run_result(run_id)


@eval_router.get("/runs/{run_id}/failures")
def get_failures(run_id: int, request: Request, limit: int = Query(50), db=Depends(_get_db)):
    from scoring_service.evaluation.service import EvaluationExecutionService
    svc = EvaluationExecutionService(db, _settings(request))
    return {"failures": svc.get_failures(run_id, limit)}


# ── Comparison & Regression ──────────────────────────────────────────

@eval_router.post("/compare")
def compare_runs(body: CompareRequest, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.service import ComparisonService
    svc = ComparisonService(db, _settings(request))
    return svc.compare_runs(body.baseline_run_id, body.candidate_run_id)


@eval_router.get("/comparisons/{comparison_id}")
def get_comparison(comparison_id: int, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.repository import ComparisonRepository
    repo = ComparisonRepository(db)
    c = repo.get(comparison_id)
    if not c:
        raise HTTPException(404, "comparison not found")
    return {
        "id": c.id, "verdict": c.verdict, "verdict_reason": c.verdict_reason,
        "metric_diffs": c.metric_diffs_json, "regression_flags": c.regression_flags,
        "improvement_flags": c.improvement_flags, "guardrail_violations": c.guardrail_violations,
    }


# ── Guardrails ───────────────────────────────────────────────────────

@eval_router.post("/guardrails", status_code=201)
def create_guardrail(body: GuardrailCreate, request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.repository import GuardrailRepository
    repo = GuardrailRepository(db)
    g = repo.create(
        tenant_id=_tenant_id(request), metric_name=body.metric_name,
        min_value=body.min_value, max_regression_delta=body.max_regression_delta,
        segment_category=body.segment_category, segment_value=body.segment_value,
        severity=body.severity,
    )
    db.commit()
    return {"id": g.id, "metric": g.metric_name, "severity": g.severity}


@eval_router.get("/guardrails")
def list_guardrails(request: Request, db=Depends(_get_db)):
    from scoring_service.evaluation.repository import GuardrailRepository
    repo = GuardrailRepository(db)
    guards = repo.list_active(_tenant_id(request))
    return {
        "guardrails": [
            {"id": g.id, "metric": g.metric_name, "min_value": g.min_value,
             "max_regression_delta": g.max_regression_delta, "severity": g.severity}
            for g in guards
        ]
    }
