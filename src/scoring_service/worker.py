"""Background worker — processes jobs, dispatches outbox, recovers stale locks."""
from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from scoring_service.circuit_breaker import CircuitBreakerError, CircuitBreakerRegistry
from scoring_service.config import Settings
from scoring_service.db.session import create_session_factory
from scoring_service.diagnostics import configure_logging
from scoring_service.failures.service import FailureService
from scoring_service.jobs.service import JobService
from scoring_service.observability import (
    JOB_COMPLETED,
    JOB_ENQUEUED,
    JOB_PROCESSING_SECONDS,
    JOB_RETRIES,
    OUTBOX_DISPATCHED,
    OUTBOX_FAILED,
)
from scoring_service.outbox.dispatcher import WebhookDispatcher
from scoring_service.outbox.service import OutboxService

logger = logging.getLogger("scoring_service")

# ── Job handlers registry ────────────────────────────────────────────

JOB_HANDLERS: dict[str, callable] = {}


def register_handler(job_type: str):
    def decorator(fn):
        JOB_HANDLERS[job_type] = fn
        return fn
    return decorator


@register_handler("score.analyze")
def handle_score_analyze(payload: dict, settings: Settings) -> dict:
    """Example job handler for async scoring analysis."""
    from scoring_service.contracts import ScoreRequest
    from scoring_service.services.scoring_service import ScoringService

    request = ScoreRequest(
        payload=payload.get("payload", {}),
        request_id=payload.get("request_id", "job"),
        source=payload.get("source", "worker"),
    )
    service = ScoringService(settings)
    result, review = service.execute(request)
    return {
        "score": result.final_score,
        "label": review.label,
        "approved": review.approved,
    }


@register_handler("noop")
def handle_noop(payload: dict, settings: Settings) -> dict:
    """Test job that does nothing."""
    return {"status": "ok"}


# ── Worker loop ──────────────────────────────────────────────────────

class Worker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._running = True
        self._engine, self._session_factory = create_session_factory(settings)
        self._dispatcher = WebhookDispatcher(settings)
        self._circuit_registry = CircuitBreakerRegistry(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout_seconds,
            half_open_max_calls=settings.circuit_breaker_half_open_max_calls,
        )

    def stop(self, *_args) -> None:
        logger.info("worker_shutdown_requested")
        self._running = False

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        logger.info("worker_started")

        cycle = 0
        while self._running:
            cycle += 1
            try:
                self._process_jobs()
                self._dispatch_outbox()
                if cycle % 12 == 0:  # every ~minute
                    self._recover_stale()
                    self._cleanup_idempotency()
            except Exception as exc:
                logger.exception("worker_cycle_error error=%s", str(exc)[:300])

            time.sleep(self.settings.job_poll_interval_seconds)

        logger.info("worker_stopped")

    def _process_jobs(self) -> None:
        if not self.settings.enable_jobs:
            return
        db = self._session_factory()
        try:
            svc = JobService(db, self.settings)
            for _ in range(self.settings.job_batch_size):
                job = svc.acquire_next()
                if not job:
                    break

                handler = JOB_HANDLERS.get(job.job_type)
                if not handler:
                    svc.fail(job, f"unknown job type: {job.job_type}")
                    db.commit()
                    continue

                start_time = time.time()
                try:
                    result = handler(job.payload, self.settings)
                    svc.complete(job, result)
                    elapsed = time.time() - start_time
                    JOB_COMPLETED.labels(job_type=job.job_type, status="succeeded").inc()
                    JOB_PROCESSING_SECONDS.labels(job_type=job.job_type).observe(elapsed)
                except Exception as exc:
                    svc.fail(job, str(exc)[:1000])
                    JOB_COMPLETED.labels(job_type=job.job_type, status="failed").inc()
                    JOB_RETRIES.labels(job_type=job.job_type).inc()

                    # Dead letter if terminal
                    if job.status == "dead":
                        fsvc = FailureService(db, self.settings)
                        fsvc.to_dead_letter(
                            source_type="job",
                            source_id=str(job.id),
                            operation=job.job_type,
                            payload_snapshot=job.payload,
                            error=str(exc)[:500],
                            correlation_id=job.correlation_id,
                        )
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("job_processing_error error=%s", str(exc)[:300])
        finally:
            db.close()

    def _dispatch_outbox(self) -> None:
        if not self.settings.enable_outbox:
            return
        db = self._session_factory()
        try:
            svc = OutboxService(db, self.settings)
            events = svc.fetch_pending()
            for event in events:
                cb = self._circuit_registry.get("webhook")
                try:
                    success, code, error = cb.call(
                        self._dispatcher.deliver, event.payload
                    )
                except CircuitBreakerError as cbe:
                    svc.mark_failed(event, str(cbe))
                    svc.record_delivery_attempt(
                        event, "webhook", "circuit_open", str(cbe)
                    )
                    OUTBOX_FAILED.inc()
                    continue

                if success:
                    svc.mark_dispatched(event)
                    svc.record_delivery_attempt(event, "webhook", "delivered", response_code=code)
                    OUTBOX_DISPATCHED.inc()
                else:
                    svc.mark_failed(event, error or "unknown")
                    svc.record_delivery_attempt(
                        event, "webhook", "failed", error, response_code=code
                    )
                    OUTBOX_FAILED.inc()

                    # Dead letter if max attempts reached
                    if event.status == "failed":
                        fsvc = FailureService(db, self.settings)
                        fsvc.to_dead_letter(
                            source_type="outbox",
                            source_id=str(event.id),
                            operation=event.event_type,
                            payload_snapshot=event.payload,
                            error=error or "dispatch_failed",
                            correlation_id=event.correlation_id,
                        )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("outbox_dispatch_error error=%s", str(exc)[:300])
        finally:
            db.close()

    def _recover_stale(self) -> None:
        db = self._session_factory()
        try:
            svc = JobService(db, self.settings)
            count = svc.recover_stale_locks()
            if count:
                db.commit()
                logger.info("stale_recovery count=%s", count)
        except Exception as exc:
            db.rollback()
            logger.exception("stale_recovery_error error=%s", str(exc)[:300])
        finally:
            db.close()

    def _cleanup_idempotency(self) -> None:
        db = self._session_factory()
        try:
            from scoring_service.idempotency.service import IdempotencyService
            svc = IdempotencyService(db, self.settings)
            count = svc.cleanup_expired()
            if count:
                logger.info("idempotency_cleanup count=%s", count)
        except Exception as exc:
            db.rollback()
            logger.exception("idempotency_cleanup_error error=%s", str(exc)[:300])
        finally:
            db.close()


def run_worker() -> None:
    settings = Settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)
    worker = Worker(settings)
    worker.run()


if __name__ == "__main__":
    run_worker()
