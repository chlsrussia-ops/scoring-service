"""FastAPI app factory with auth, rate limiting, metrics, DB."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from scoring_service.config import Settings
from scoring_service.diagnostics import configure_logging
from scoring_service.security import require_api_key
from scoring_service.rate_limit import enforce_rate_limit
from scoring_service.services.scoring_service import ScoringService
from scoring_service.contracts import ScoreRequest
from scoring_service.repos.score_repo import ScoreRepository
from scoring_service.observability import REQUEST_COUNTER, SCORE_COUNTER, SCORE_HISTOGRAM

def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)

    app = FastAPI(title=settings.app_name, version="3.0.0")
    app.state.settings = settings

    # DB setup
    try:
        from scoring_service.db.session import create_session_factory
        engine, session_factory = create_session_factory(settings)
        app.state.engine = engine
        app.state.session_factory = session_factory
    except Exception:
        app.state.engine = None
        app.state.session_factory = None

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "3.0.0"}

    @app.get("/ready")
    async def ready():
        checks = {"db": "ok" if app.state.engine else "unavailable"}
        return {"status": "ready" if checks["db"] == "ok" else "degraded", "checks": checks}

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/v1/score", dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)])
    async def score(body: ScoreRequest):
        REQUEST_COUNTER.labels(operation="score", status="started").inc()
        service = ScoringService(settings)
        result, review = service.execute(body)
        SCORE_COUNTER.labels(review_label=review.label).inc()
        SCORE_HISTOGRAM.observe(result.final_score)

        # Persist if DB available
        if app.state.session_factory:
            try:
                db = app.state.session_factory()
                repo = ScoreRepository(db)
                repo.save(
                    request_id=result.request_id, source=result.source,
                    payload=body.payload, final_score=result.final_score,
                    capped=result.capped, used_fallback=result.used_fallback,
                    reason=result.reason, review_label=review.label,
                    approved=review.approved, diagnostics=list(result.diagnostics))
                db.close()
            except Exception:
                pass  # DB failure should not break scoring

        REQUEST_COUNTER.labels(operation="score", status="completed").inc()
        return {"result": result.model_dump(), "review": review.model_dump()}

    @app.get("/v1/scores")
    async def list_scores():
        if not app.state.session_factory:
            return {"records": [], "note": "DB unavailable"}
        db = app.state.session_factory()
        repo = ScoreRepository(db)
        records = repo.list_recent(50)
        db.close()
        return {"records": [{"id": r.id, "request_id": r.request_id, "score": r.final_score,
                              "label": r.review_label, "approved": r.approved} for r in records]}

    return app
