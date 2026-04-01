"""FastAPI app factory — scoring-service with production hardening v2."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy.exc import IntegrityError
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


@contextmanager
def _db_session(session_factory):
    """Context manager that guarantees session close and rollback on error."""
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
        version="4.2.0",
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
        return {"status": "ok", "version": "4.2.0", "product": "TrendIntel"}

    @app.get("/ready")
    async def ready():
        checks: dict = {"db": "ok" if app.state.engine else "unavailable"}
        if app.state.session_factory:
            try:
                with _db_session(app.state.session_factory) as db:
                    from scoring_service.db.models import JobRecord

                    osvc = OutboxService(db, settings)
                    pending = osvc.count_pending()
                    checks["outbox_pending"] = pending
                    if pending > 100:
                        checks["outbox"] = "backlog"

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

                    # Dead jobs backlog
                    from scoring_service.jobs.service import JobService, DEAD
                    job_svc = JobService(db, settings)
                    counts = job_svc.count_by_status()
                    dead_count = counts.get(DEAD, 0)
                    checks["dead_jobs"] = dead_count

                    # DLQ depth
                    from scoring_service.failures.service import FailureService
                    fsvc = FailureService(db, settings)
                    dlq = fsvc.count_by_status()
                    checks["dlq_depth"] = sum(dlq.values())
            except Exception as exc:
                checks["db"] = "error"
                checks["db_error"] = str(exc)[:100]

        overall = "ready"
        if checks["db"] != "ok":
            overall = "not_ready"
        elif (
            checks.get("stale_locks", 0) > 0
            or checks.get("quarantined_sources", 0) > 0
            or checks.get("dead_jobs", 0) > 20
            or checks.get("dlq_depth", 0) > 50
        ):
            overall = "degraded"
        return {"status": overall, "checks": checks}

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # ── Score endpoint (backward compatible + production hardened v2) ──

    @app.post(
        "/v1/score",
        dependencies=[Depends(require_api_key), Depends(enforce_rate_limit), Depends(check_body_size)],
    )
    async def score(body: ScoreRequest, request: Request):
        REQUEST_COUNTER.labels(operation="score", status="started").inc()
        SOURCE_REQUESTS.labels(source=body.source).inc()
        cid = get_correlation_id()

        if not app.state.session_factory:
            # No DB — score in-memory only
            service = ScoringService(settings)
            result, review = service.execute(body)
            SCORE_COUNTER.labels(review_label=review.label).inc()
            SCORE_HISTOGRAM.observe(result.final_score)
            REQUEST_COUNTER.labels(operation="score", status="completed").inc()
            return {"result": result.model_dump(), "review": review.model_dump()}

        # ── Source quarantine check ──
        if settings.enable_source_protection:
            with _db_session(app.state.session_factory) as db:
                sps = SourceProtectionService(db, settings)
                if sps.is_quarantined(body.source):
                    SOURCE_ERRORS.labels(source=body.source).inc()
                    REQUEST_COUNTER.labels(operation="score", status="quarantined").inc()
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "source_quarantined",
                            "detail": f"Source '{body.source}' is temporarily quarantined",
                        },
                    )

        # ── Idempotency check ──
        idempotency_key = request.headers.get("Idempotency-Key")

        if idempotency_key and settings.enable_idempotency:
            try:
                with _db_session(app.state.session_factory) as db:
                    idem_svc = IdempotencyService(db, settings)
                    existing = idem_svc.check(idempotency_key, "score", body.payload)
                    if existing and existing.status == "completed" and existing.response_body:
                        logger.info("idempotent_hit key=%s cid=%s", idempotency_key, cid)
                        return existing.response_body
                    if existing and existing.status == "processing":
                        return JSONResponse(
                            status_code=409,
                            content={"error": "request_in_progress", "idempotency_key": idempotency_key},
                        )
                    # Start new — handle concurrent race via IntegrityError
                    try:
                        idem_svc.start(idempotency_key, "score", body.payload)
                    except IntegrityError:
                        db.rollback()
                        existing = idem_svc.check(idempotency_key, "score", body.payload)
                        if existing and existing.status == "completed" and existing.response_body:
                            return existing.response_body
            except Exception as exc:
                logger.warning("idempotency_check_error key=%s error=%s", idempotency_key, str(exc)[:200])

        # ── Execute scoring ──
        service = ScoringService(settings)
        result, review = service.execute(body)
        SCORE_COUNTER.labels(review_label=review.label).inc()
        SCORE_HISTOGRAM.observe(result.final_score)

        response_data = {"result": result.model_dump(), "review": review.model_dump()}

        # ── Persist + outbox in same transaction ──
        try:
            with _db_session(app.state.session_factory) as db:
                repo = ScoreRepository(db)
                try:
                    repo.save(
                        request_id=result.request_id, source=result.source,
                        payload=body.payload, final_score=result.final_score,
                        capped=result.capped, used_fallback=result.used_fallback,
                        reason=result.reason, review_label=review.label,
                        approved=review.approved, diagnostics=list(result.diagnostics),
                    )
                except IntegrityError:
                    # Duplicate request_id — idempotent: return result without error
                    db.rollback()
                    logger.info("duplicate_request_id id=%s cid=%s", result.request_id, cid)
                    REQUEST_COUNTER.labels(operation="score", status="completed").inc()
                    return response_data

                # Outbox in same transaction
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

                # Complete idempotency
                if idempotency_key and settings.enable_idempotency:
                    idem_svc = IdempotencyService(db, settings)
                    rec = idem_svc.check(idempotency_key, "score", body.payload)
                    if rec:
                        idem_svc.complete(rec, 200, response_data)

                # Source health
                if settings.enable_source_protection:
                    sps = SourceProtectionService(db, settings)
                    if result.ok:
                        sps.record_success(body.source)
                    else:
                        sps.record_failure(body.source, result.reason or "scoring_failure")

        except Exception as exc:
            logger.warning("db_persist_error error=%s cid=%s", str(exc)[:200], cid)
            # Record failure in separate session
            try:
                with _db_session(app.state.session_factory) as db2:
                    from scoring_service.failures.service import FailureService
                    fsvc = FailureService(db2, settings)
                    fsvc.record_failure(
                        entity_type="score", entity_id=result.request_id,
                        operation="persist", error=str(exc)[:500], correlation_id=cid,
                    )
            except Exception:
                logger.exception("failure_record_error cid=%s", cid)

        REQUEST_COUNTER.labels(operation="score", status="completed").inc()
        return response_data

    @app.get("/v1/scores")
    async def list_scores():
        if not app.state.session_factory:
            return {"records": [], "note": "DB unavailable"}
        with _db_session(app.state.session_factory) as db:
            repo = ScoreRepository(db)
            records = repo.list_recent(50)
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


    # ── Stage 3: Platform API (multi-tenancy, policies, pipeline, usage) ──
    try:
        from scoring_service.plugins.registry import plugin_registry
        from scoring_service.plugins.builtin import register_builtins
        register_builtins(plugin_registry)

        from scoring_service.platform_api.routes import platform_router, platform_admin_router
        app.include_router(platform_router)
        app.include_router(platform_admin_router)
        logger.info("platform_api_registered routes=platform+admin")
    except ImportError as exc:
        logger.warning("platform_api_not_available error=%s", exc)



    # ── Stage 6: Ranking Evaluation Framework ──
    try:
        from scoring_service.evaluation.routes import eval_router
        app.include_router(eval_router)
        logger.info("evaluation_api_registered routes=eval")
    except ImportError as exc:
        logger.warning("evaluation_api_not_available error=%s", exc)

    # ── Stage 5: Adaptation & Self-Improving System ──
    try:
        from scoring_service.adaptation.routes import adaptation_router, adaptation_admin_router
        app.include_router(adaptation_router)
        app.include_router(adaptation_admin_router)
        logger.info('adaptation_api_registered routes=adaptation+admin')
    except ImportError as exc:
        logger.warning('adaptation_api_not_available error=%s', exc)

    return app
