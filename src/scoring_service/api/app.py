"""FastAPI app factory — scoring-service with dashboard, sources, LLM, demo + production hardening."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from scoring_service.admin.routes import admin_router
from scoring_service.circuit_breaker import CircuitBreakerRegistry
from scoring_service.config import Settings
from scoring_service.contracts import ScoreRequest
from scoring_service.correlation import CorrelationMiddleware, get_correlation_id
from scoring_service.diagnostics import configure_logging
from scoring_service.idempotency.service import IdempotencyService
from scoring_service.observability import (
    REQUEST_COUNTER,
    SCORE_COUNTER,
    SCORE_HISTOGRAM,
    SOURCE_ERRORS,
    SOURCE_REQUESTS,
)
from scoring_service.outbox.service import OutboxService
from scoring_service.rate_limit import enforce_rate_limit
from scoring_service.repos.score_repo import ScoreRepository
from scoring_service.security import check_body_size, require_api_key
from scoring_service.services.scoring_service import ScoringService
from scoring_service.source_protection import SourceProtectionService

logger = logging.getLogger("scoring_service")


def create_app() -> FastAPI:
    settings = Settings()

    # ── Fail-fast config validation (prod only) ──
    config_errors = settings.validate_config()
    if config_errors and settings.env == "prod":
        import sys
        for err in config_errors:
            print(f"CONFIG ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    configure_logging(settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title="TrendIntel - Content Intelligence Platform",
        description="AI-powered trend intelligence for content, media, and marketing teams",
        version="4.1.0",
    )
    app.state.settings = settings

    # ── Correlation ID middleware ──
    app.add_middleware(CorrelationMiddleware)

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Circuit breaker registry ──
    app.state.circuit_registry = CircuitBreakerRegistry(
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout=settings.circuit_breaker_recovery_timeout_seconds,
        half_open_max_calls=settings.circuit_breaker_half_open_max_calls,
    )

    # ── DB setup ──
    try:
        from scoring_service.db.session import create_session_factory
        engine, session_factory = create_session_factory(settings)
        app.state.engine = engine
        app.state.session_factory = session_factory
    except Exception as exc:
        logger.warning("db_init_failed error=%s", exc)
        app.state.engine = None
        app.state.session_factory = None

    # ── Admin router ──
    app.include_router(admin_router)

    # ── Health / Ready / Metrics ──

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "4.1.0", "product": "TrendIntel"}

    @app.get("/ready")
    async def ready():
        checks: dict = {"db": "ok" if app.state.engine else "unavailable"}
        if app.state.session_factory:
            try:
                db = app.state.session_factory()
                osvc = OutboxService(db, settings)
                pending = osvc.count_pending()
                checks["outbox_pending"] = pending
                if pending > 100:
                    checks["outbox"] = "backlog"

                from scoring_service.db.models import JobRecord
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                stale = (
                    db.query(JobRecord)
                    .filter(JobRecord.status == "running", JobRecord.leased_until < now)
                    .count()
                )
                checks["stale_locks"] = stale
                sps = SourceProtectionService(db, settings)
                quarantined = len(sps.list_quarantined())
                checks["quarantined_sources"] = quarantined
                db.close()
            except Exception:
                checks["db"] = "error"

        overall = "ready"
        if checks["db"] != "ok":
            overall = "degraded"
        elif checks.get("stale_locks", 0) > 0 or checks.get("quarantined_sources", 0) > 0:
            overall = "degraded"
        return {"status": overall, "checks": checks}

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # ── Score endpoint (backward compatible + production hardened) ──

    @app.post(
        "/v1/score",
        dependencies=[Depends(require_api_key), Depends(enforce_rate_limit), Depends(check_body_size)],
    )
    async def score(body: ScoreRequest, request: Request):
        REQUEST_COUNTER.labels(operation="score", status="started").inc()
        SOURCE_REQUESTS.labels(source=body.source).inc()
        cid = get_correlation_id()

        # ── Source quarantine check ──
        if app.state.session_factory and settings.enable_source_protection:
            db = app.state.session_factory()
            try:
                sps = SourceProtectionService(db, settings)
                if sps.is_quarantined(body.source):
                    db.close()
                    SOURCE_ERRORS.labels(source=body.source).inc()
                    return {
                        "error": "source_quarantined",
                        "detail": f"Source '{body.source}' is temporarily quarantined",
                    }
            finally:
                db.close()

        # ── Idempotency check ──
        idempotency_key = request.headers.get("Idempotency-Key")
        idem_record = None

        if idempotency_key and app.state.session_factory and settings.enable_idempotency:
            db = app.state.session_factory()
            try:
                idem_svc = IdempotencyService(db, settings)
                existing = idem_svc.check(idempotency_key, "score", body.payload)
                if existing and existing.status == "completed":
                    db.close()
                    logger.info("idempotent_hit key=%s cid=%s", idempotency_key, cid)
                    return existing.response_body
                idem_record = idem_svc.start(idempotency_key, "score", body.payload)
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()

        # ── Execute scoring ──
        service = ScoringService(settings)
        result, review = service.execute(body)
        SCORE_COUNTER.labels(review_label=review.label).inc()
        SCORE_HISTOGRAM.observe(result.final_score)

        response_data = {"result": result.model_dump(), "review": review.model_dump()}

        # ── Persist + outbox in same transaction ──
        if app.state.session_factory:
            db = app.state.session_factory()
            try:
                repo = ScoreRepository(db)
                repo.save(
                    request_id=result.request_id, source=result.source,
                    payload=body.payload, final_score=result.final_score,
                    capped=result.capped, used_fallback=result.used_fallback,
                    reason=result.reason, review_label=review.label,
                    approved=review.approved, diagnostics=list(result.diagnostics),
                )

                if settings.enable_outbox:
                    outbox = OutboxService(db, settings)
                    outbox.publish(
                        event_type="score.completed",
                        aggregate_type="score",
                        aggregate_id=result.request_id,
                        payload={
                            "request_id": result.request_id,
                            "source": result.source,
                            "score": result.final_score,
                            "review_label": review.label,
                            "approved": review.approved,
                        },
                        correlation_id=cid,
                    )

                if idem_record and idempotency_key:
                    idem_svc2 = IdempotencyService(db, settings)
                    rec = idem_svc2.check(idempotency_key, "score", body.payload)
                    if rec:
                        idem_svc2.complete(rec, 200, response_data)

                if settings.enable_source_protection:
                    sps = SourceProtectionService(db, settings)
                    if result.ok:
                        sps.record_success(body.source)
                    else:
                        sps.record_failure(body.source, result.reason or "scoring_failure")

                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning("db_persist_error error=%s cid=%s", str(exc)[:200], cid)
                try:
                    db2 = app.state.session_factory()
                    from scoring_service.failures.service import FailureService
                    fsvc = FailureService(db2, settings)
                    fsvc.record_failure(
                        entity_type="score", entity_id=result.request_id,
                        operation="persist", error=str(exc)[:500], correlation_id=cid,
                    )
                    db2.commit()
                    db2.close()
                except Exception:
                    pass
            finally:
                db.close()

        REQUEST_COUNTER.labels(operation="score", status="completed").inc()
        return response_data

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

    # ── Register existing routers ──
    if app.state.session_factory:
        try:
            from scoring_service.api.dashboard import router as dashboard_router
            from scoring_service.api.sources_api import router as sources_router
            from scoring_service.api.llm_api import router as llm_router
            from scoring_service.api.demo_api import router as demo_router

            app.include_router(dashboard_router)
            app.include_router(sources_router)
            app.include_router(llm_router)
            app.include_router(demo_router)
        except ImportError:
            pass

    return app
