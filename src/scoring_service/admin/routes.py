"""Admin / Ops API v2 — proper HTTP codes, job enqueue, audit log, circuit breaker control."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from scoring_service.audit import AuditService
from scoring_service.config import Settings
from scoring_service.failures.service import FailureService
from scoring_service.jobs.service import DEAD, JobService
from scoring_service.observability import (
    DLQ_DEPTH,
    JOB_QUEUE_DEPTH,
    OUTBOX_PENDING,
    SOURCES_QUARANTINED,
)
from scoring_service.outbox.service import OutboxService
from scoring_service.security import require_admin_key
from scoring_service.source_protection import SourceProtectionService

admin_router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)


def _get_db(request: Request):
    if not request.app.state.session_factory:
        raise HTTPException(503, "database unavailable")
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _actor(request: Request) -> str:
    return request.headers.get("x-admin-key", "admin")[:8] + "..."


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ── Pydantic models for request bodies ────────────────────────────────

class JobEnqueueRequest(BaseModel):
    job_type: str
    payload: dict[str, Any] = {}
    max_attempts: int | None = None
    priority: int = 0


# ── Jobs ─────────────────────────────────────────────────────────────

@admin_router.get("/jobs")
def list_jobs(
    request: Request,
    status: str | None = Query(None),
    job_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = JobService(db, _settings(request))
    jobs = svc.list_jobs(status=status, job_type=job_type, limit=limit, offset=offset)
    return {
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "last_error": j.last_error,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "next_attempt_at": j.next_attempt_at.isoformat() if j.next_attempt_at else None,
                "correlation_id": j.correlation_id,
            }
            for j in jobs
        ],
        "count": len(jobs),
    }


@admin_router.post("/jobs", status_code=201)
def enqueue_job(
    request: Request,
    body: JobEnqueueRequest,
    db=Depends(_get_db),
) -> dict[str, Any]:
    """Enqueue a new job via admin API."""
    from scoring_service.correlation import get_correlation_id
    svc = JobService(db, _settings(request))
    job = svc.enqueue(
        body.job_type,
        body.payload,
        max_attempts=body.max_attempts,
        priority=body.priority,
        correlation_id=get_correlation_id(),
    )
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="job_enqueue",
        target_type="job", target_id=str(job.id),
        details={"job_type": body.job_type}, ip_address=_ip(request),
    )
    db.commit()
    return {"status": "enqueued", "job_id": job.id, "job_type": job.job_type}


@admin_router.get("/jobs/{job_id}")
def get_job(
    request: Request,
    job_id: int,
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = JobService(db, _settings(request))
    job = svc.get_job(job_id)
    if not job:
        raise HTTPException(404, f"job {job_id} not found")
    attempts = svc.get_attempts(job_id)
    return {
        "job": {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "payload": job.payload,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "last_error": job.last_error,
            "result": job.result,
            "locked_by": job.locked_by,
            "leased_until": job.leased_until.isoformat() if job.leased_until else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "correlation_id": job.correlation_id,
        },
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "status": a.status,
                "error": a.error,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "finished_at": a.finished_at.isoformat() if a.finished_at else None,
            }
            for a in attempts
        ],
    }


@admin_router.post("/jobs/{job_id}/retry")
def retry_job(
    request: Request,
    job_id: int,
    db=Depends(_get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    svc = JobService(db, settings)
    job = svc.get_job(job_id)
    if not job:
        raise HTTPException(404, f"job {job_id} not found")
    retried = svc.retry_job(job_id)
    if not retried:
        raise HTTPException(
            409, f"job {job_id} is in '{job.status}' state, cannot retry (must be dead/failed)"
        )
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="job_retry",
        target_type="job", target_id=str(job_id), ip_address=_ip(request),
    )
    db.commit()
    return {"status": "requeued", "job_id": retried.id, "new_status": retried.status}


@admin_router.post("/jobs/requeue-failed")
def requeue_failed_jobs(
    request: Request,
    db=Depends(_get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    svc = JobService(db, settings)
    count = svc.requeue_all_failed()
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="jobs_requeue_all_failed",
        target_type="job", target_id="all",
        details={"count": count}, ip_address=_ip(request),
    )
    db.commit()
    return {"status": "requeued", "count": count}


# ── Failures / DLQ ───────────────────────────────────────────────────

@admin_router.get("/failures")
def list_failures(
    request: Request,
    source_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = FailureService(db, _settings(request))
    dlq = svc.list_dead_letter(source_type=source_type, limit=limit, offset=offset)
    failures = svc.list_failures(entity_type=entity_type, limit=limit, offset=offset)
    return {
        "dead_letter": [
            {
                "id": d.id,
                "source_type": d.source_type,
                "source_id": d.source_id,
                "operation": d.operation,
                "error": d.error[:500],
                "status": d.status,
                "retry_count": d.retry_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in dlq
        ],
        "failure_records": [
            {
                "id": f.id,
                "entity_type": f.entity_type,
                "entity_id": f.entity_id,
                "operation": f.operation,
                "error": f.error[:500],
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in failures
        ],
    }


@admin_router.post("/failures/{item_id}/replay")
def replay_failure(
    request: Request,
    item_id: int,
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = FailureService(db, _settings(request))
    item = svc.get_dead_letter_item(item_id)
    if not item:
        raise HTTPException(404, f"dead letter item {item_id} not found")
    replayed = svc.replay_dead_letter(item_id)
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="dlq_replay",
        target_type="dead_letter", target_id=str(item_id), ip_address=_ip(request),
    )
    db.commit()
    return {"status": "replayed", "item_id": replayed.id, "new_status": replayed.status}


# ── Outbox ───────────────────────────────────────────────────────────

@admin_router.get("/outbox")
def list_outbox(
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = OutboxService(db, _settings(request))
    events = svc.list_events(status=status, limit=limit, offset=offset)
    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "aggregate_type": e.aggregate_type,
                "aggregate_id": e.aggregate_id,
                "status": e.status,
                "dispatch_attempts": e.dispatch_attempts,
                "dispatch_error": e.dispatch_error,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "dispatched_at": e.dispatched_at.isoformat() if e.dispatched_at else None,
                "correlation_id": e.correlation_id,
            }
            for e in events
        ],
        "count": len(events),
    }


@admin_router.post("/outbox/{event_id}/dispatch")
def dispatch_outbox_event(
    request: Request,
    event_id: int,
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = OutboxService(db, _settings(request))
    event = svc.dispatch_single(event_id)
    if not event:
        raise HTTPException(404, f"outbox event {event_id} not found")
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="outbox_dispatch",
        target_type="outbox_event", target_id=str(event_id), ip_address=_ip(request),
    )
    db.commit()
    return {"status": "queued_for_dispatch", "event_id": event.id}


# ── Sources ──────────────────────────────────────────────────────────

@admin_router.get("/sources/health")
def sources_health(
    request: Request,
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = SourceProtectionService(db, _settings(request))
    return svc.summary()


@admin_router.post("/sources/{source_id}/quarantine")
def quarantine_source(
    request: Request,
    source_id: str,
    reason: str = Query("manual quarantine"),
    duration_seconds: int | None = Query(None),
    db=Depends(_get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    svc = SourceProtectionService(db, settings)
    state = svc.quarantine(source_id, reason, duration_seconds, created_by=_actor(request))
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="source_quarantine",
        target_type="source", target_id=source_id,
        details={"reason": reason}, ip_address=_ip(request),
    )
    db.commit()
    return {
        "status": "quarantined", "source": source_id,
        "until": state.quarantined_until.isoformat() if state.quarantined_until else None,
    }


@admin_router.post("/sources/{source_id}/resume")
def resume_source(
    request: Request,
    source_id: str,
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = SourceProtectionService(db, _settings(request))
    state = svc.resume(source_id)
    if not state:
        raise HTTPException(404, f"source '{source_id}' not found")
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="source_resume",
        target_type="source", target_id=source_id, ip_address=_ip(request),
    )
    db.commit()
    return {"status": "resumed", "source": source_id}


# ── Audit Log ────────────────────────────────────────────────────────

@admin_router.get("/audit")
def list_audit(
    request: Request,
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(_get_db),
) -> dict[str, Any]:
    svc = AuditService(db)
    entries = svc.list_recent(action=action, target_type=target_type, limit=limit, offset=offset)
    return {
        "entries": [
            {
                "id": e.id,
                "actor": e.actor,
                "action": e.action,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "details": e.details,
                "correlation_id": e.correlation_id,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
        "count": len(entries),
    }


# ── Circuit Breakers ─────────────────────────────────────────────────

@admin_router.get("/circuit-breakers")
def list_circuit_breakers(request: Request) -> dict[str, Any]:
    if not hasattr(request.app.state, "circuit_registry"):
        return {"breakers": []}
    return {"breakers": request.app.state.circuit_registry.all_snapshots()}


@admin_router.post("/circuit-breakers/{name}/reset")
def reset_circuit_breaker(
    request: Request,
    name: str,
    db=Depends(_get_db),
) -> dict[str, Any]:
    if not hasattr(request.app.state, "circuit_registry"):
        raise HTTPException(404, "circuit breaker registry not initialized")
    cb = request.app.state.circuit_registry.get(name)
    cb.reset()
    audit = AuditService(db)
    audit.log(
        actor=_actor(request), action="circuit_breaker_reset",
        target_type="circuit_breaker", target_id=name, ip_address=_ip(request),
    )
    db.commit()
    return {"status": "reset", "name": name, "new_state": cb.state.value}


# ── Idempotency ──────────────────────────────────────────────────────

@admin_router.post("/idempotency/cleanup")
def cleanup_idempotency(
    request: Request,
    db=Depends(_get_db),
) -> dict[str, Any]:
    from scoring_service.idempotency.service import IdempotencyService
    svc = IdempotencyService(db, _settings(request))
    count = svc.cleanup_expired()
    db.commit()
    return {"status": "cleaned", "removed": count}


# ── Diagnostics ──────────────────────────────────────────────────────

@admin_router.get("/diagnostics/summary")
def diagnostics_summary(
    request: Request,
    db=Depends(_get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    job_svc = JobService(db, settings)
    outbox_svc = OutboxService(db, settings)
    failure_svc = FailureService(db, settings)
    source_svc = SourceProtectionService(db, settings)

    job_counts = job_svc.count_by_status()
    dlq_counts = failure_svc.count_by_status()
    source_summary = source_svc.summary()

    now = datetime.now(timezone.utc)
    from scoring_service.db.models import JobRecord
    stale_count = (
        db.query(JobRecord)
        .filter(JobRecord.status == "running", JobRecord.leased_until < now)
        .count()
    )

    pending_outbox = outbox_svc.count_pending()
    failed_outbox = outbox_svc.count_failed()

    # Update gauges
    JOB_QUEUE_DEPTH.set(job_counts.get("queued", 0) + job_counts.get("retrying", 0))
    OUTBOX_PENDING.set(pending_outbox)
    DLQ_DEPTH.set(sum(dlq_counts.values()))
    SOURCES_QUARANTINED.set(source_summary["quarantined"])

    degraded_reasons: list[str] = []
    if stale_count > 0:
        degraded_reasons.append(f"{stale_count} stale job locks")
    dead_jobs = job_counts.get("dead", 0)
    if dead_jobs > 10:
        degraded_reasons.append(f"{dead_jobs} dead jobs")
    if pending_outbox > 100:
        degraded_reasons.append(f"{pending_outbox} pending outbox events (backlog)")
    if failed_outbox > 0:
        degraded_reasons.append(f"{failed_outbox} failed outbox events")
    if source_summary["quarantined"] > 0:
        degraded_reasons.append(f"{source_summary['quarantined']} quarantined sources")
    dlq_total = sum(dlq_counts.values())
    if dlq_total > 0:
        degraded_reasons.append(f"{dlq_total} items in dead letter queue")

    cb_snapshots = []
    if hasattr(request.app.state, "circuit_registry"):
        cb_snapshots = request.app.state.circuit_registry.all_snapshots()
        open_cbs = [s for s in cb_snapshots if s["state"] == "open"]
        if open_cbs:
            degraded_reasons.append(f"{len(open_cbs)} circuit breakers open")

    # Failure records count (last 24h)
    from scoring_service.db.models import FailureRecord
    from datetime import timedelta
    recent_failures = (
        db.query(FailureRecord)
        .filter(FailureRecord.created_at >= now - timedelta(hours=24))
        .count()
    )

    return {
        "status": "degraded" if degraded_reasons else "healthy",
        "degraded_reasons": degraded_reasons,
        "jobs": job_counts,
        "stale_locks": stale_count,
        "outbox": {"pending": pending_outbox, "failed": failed_outbox},
        "dead_letter": dlq_counts,
        "recent_failures_24h": recent_failures,
        "sources": source_summary,
        "circuit_breakers": cb_snapshots,
        "config": {
            "env": settings.env,
            "idempotency": settings.enable_idempotency,
            "jobs": settings.enable_jobs,
            "outbox": settings.enable_outbox,
            "circuit_breaker": settings.enable_circuit_breaker,
            "source_protection": settings.enable_source_protection,
        },
    }
