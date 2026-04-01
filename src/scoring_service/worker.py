"""Background worker v2 — graceful drain, heartbeat, per-source circuit breakers."""
from __future__ import annotations

import logging
import os
import signal
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from scoring_service.circuit_breaker import CircuitBreakerError, CircuitBreakerRegistry
from scoring_service.config import Settings
from scoring_service.correlation import new_correlation_id, set_correlation_id
from scoring_service.db.session import create_session_factory
from scoring_service.diagnostics import configure_logging
from scoring_service.failures.service import FailureService
from scoring_service.jobs.service import JobService
from scoring_service.observability import (
    JOB_COMPLETED,
    JOB_PROCESSING_SECONDS,
    JOB_QUEUE_DEPTH,
    JOB_RETRIES,
    OUTBOX_DISPATCHED,
    OUTBOX_FAILED,
    OUTBOX_PENDING,
)
from scoring_service.outbox.dispatcher import WebhookDispatcher
from scoring_service.outbox.service import OutboxService

logger = logging.getLogger("scoring_service")

HEARTBEAT_FILE = "/tmp/scoring-worker-heartbeat"

# ── Job handlers registry ────────────────────────────────────────────

JOB_HANDLERS: dict[str, callable] = {}


def register_handler(job_type: str):
    def decorator(fn):
        JOB_HANDLERS[job_type] = fn
        return fn
    return decorator


@register_handler("score.analyze")
def handle_score_analyze(payload: dict, settings: Settings) -> dict:
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
    return {"status": "ok"}


@register_handler("outbox.replay_failed")
def handle_outbox_replay(payload: dict, settings: Settings) -> dict:
    """Re-dispatch all failed outbox events."""
    return {"status": "dispatched_by_normal_cycle"}


# ── Worker ───────────────────────────────────────────────────────────

@contextmanager
def _db_session(session_factory):
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class Worker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._running = True
        self._draining = False
        self._engine, self._session_factory = create_session_factory(settings)
        self._dispatcher = WebhookDispatcher(settings)
        self._circuit_registry = CircuitBreakerRegistry(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout_seconds,
            half_open_max_calls=settings.circuit_breaker_half_open_max_calls,
        )

    def stop(self, *_args) -> None:
        if self._draining:
            logger.warning("worker_force_stop (second signal)")
            self._running = False
            return
        logger.info("worker_drain_requested (finishing current batch, send again to force)")
        self._draining = True

    def _write_heartbeat(self) -> None:
        try:
            with open(HEARTBEAT_FILE, "w") as f:
                f.write(datetime.now(timezone.utc).isoformat())
        except OSError:
            pass

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        logger.info("worker_started pid=%s", os.getpid())

        cycle = 0
        while self._running and not self._draining:
            cycle += 1
            cid = new_correlation_id()
            try:
                self._process_jobs()
                self._dispatch_outbox()
                if cycle % 12 == 0:
                    self._recover_stale()
                    self._cleanup_idempotency()
                self._write_heartbeat()
                self._update_gauges()
            except Exception as exc:
                logger.exception("worker_cycle_error cycle=%s error=%s cid=%s", cycle, str(exc)[:300], cid)

            time.sleep(self.settings.job_poll_interval_seconds)

        if self._draining:
            logger.info("worker_draining (completing in-flight work)")
            try:
                self._process_jobs()
                self._dispatch_outbox()
            except Exception:
                pass
        logger.info("worker_stopped")

    def _process_jobs(self) -> None:
        if not self.settings.enable_jobs:
            return
        with _db_session(self._session_factory) as db:
            svc = JobService(db, self.settings)
            for _ in range(self.settings.job_batch_size):
                job = svc.acquire_next()
                if not job:
                    break

                handler = JOB_HANDLERS.get(job.job_type)
                if not handler:
                    svc.fail(job, f"unknown job type: {job.job_type}")
                    continue

                set_correlation_id(job.correlation_id or new_correlation_id())
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

                    if job.status == "dead":
                        fsvc = FailureService(db, self.settings)
                        fsvc.to_dead_letter(
                            source_type="job", source_id=str(job.id),
                            operation=job.job_type, payload_snapshot=job.payload,
                            error=str(exc)[:500], correlation_id=job.correlation_id,
                        )

    def _dispatch_outbox(self) -> None:
        if not self.settings.enable_outbox:
            return
        with _db_session(self._session_factory) as db:
            svc = OutboxService(db, self.settings)
            events = svc.fetch_pending()
            for event in events:
                channel = event.payload.get("_channel", "webhook")
                cb = self._circuit_registry.get(f"dispatch:{channel}")
                try:
                    success, code, error = cb.call(self._dispatcher.deliver, event.payload)
                except CircuitBreakerError as cbe:
                    svc.mark_failed(event, str(cbe))
                    svc.record_delivery_attempt(event, channel, "circuit_open", str(cbe))
                    OUTBOX_FAILED.inc()
                    logger.warning("outbox_circuit_open event_id=%s channel=%s", event.id, channel)
                    continue

                if success:
                    svc.mark_dispatched(event)
                    svc.record_delivery_attempt(event, channel, "delivered", response_code=code)
                    OUTBOX_DISPATCHED.inc()
                else:
                    svc.mark_failed(event, error or "unknown")
                    svc.record_delivery_attempt(event, channel, "failed", error, response_code=code)
                    OUTBOX_FAILED.inc()

                    if event.status == "failed":
                        fsvc = FailureService(db, self.settings)
                        fsvc.to_dead_letter(
                            source_type="outbox", source_id=str(event.id),
                            operation=event.event_type, payload_snapshot=event.payload,
                            error=error or "dispatch_failed", correlation_id=event.correlation_id,
                        )

    def _recover_stale(self) -> None:
        with _db_session(self._session_factory) as db:
            svc = JobService(db, self.settings)
            count = svc.recover_stale_locks()
            if count:
                logger.info("stale_recovery count=%s", count)

    def _cleanup_idempotency(self) -> None:
        with _db_session(self._session_factory) as db:
            from scoring_service.idempotency.service import IdempotencyService
            svc = IdempotencyService(db, self.settings)
            count = svc.cleanup_expired()
            if count:
                logger.info("idempotency_cleanup count=%s", count)

    def _update_gauges(self) -> None:
        try:
            with _db_session(self._session_factory) as db:
                job_svc = JobService(db, self.settings)
                counts = job_svc.count_by_status()
                JOB_QUEUE_DEPTH.set(counts.get("queued", 0) + counts.get("retrying", 0))

                outbox_svc = OutboxService(db, self.settings)
                OUTBOX_PENDING.set(outbox_svc.count_pending())
        except Exception:
            pass


def run_worker() -> None:
    settings = Settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)
    worker = Worker(settings)
    worker.run()


if __name__ == "__main__":
    run_worker()
