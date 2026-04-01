"""Comprehensive tests v2 for production hardening improvements."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from scoring_service.audit import AuditService
from scoring_service.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
)
from scoring_service.config import Settings
from scoring_service.correlation import get_correlation_id, new_correlation_id, set_correlation_id
from scoring_service.db.models import (
    AuditLog,
    Base,
    DeadLetterItem,
    IdempotencyRecord,
    JobAttempt,
    JobRecord,
    OutboxEvent,
    SourceHealthState,
)
from scoring_service.failures.service import FailureService
from scoring_service.idempotency.service import IdempotencyService
from scoring_service.jobs.service import DEAD, QUEUED, RETRYING, RUNNING, SUCCEEDED, JobService
from scoring_service.outbox.service import OutboxService
from scoring_service.security import redact_dict
from scoring_service.source_protection import SourceProtectionService


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        job_max_attempts=3,
        job_backoff_base_seconds=0.01,
        job_backoff_max_seconds=0.1,
        job_backoff_jitter=False,
        job_stale_lock_timeout_seconds=1,
        job_lease_duration_seconds=1,
        source_quarantine_error_threshold=3,
        source_quarantine_duration_seconds=60,
        outbox_max_dispatch_attempts=3,
        idempotency_ttl_seconds=3600,
    )


# ── Idempotency Tests ───────────────────────────────────────────────


class TestIdempotency:
    def test_new_key_returns_none(self, db: Session, settings: Settings) -> None:
        svc = IdempotencyService(db, settings)
        result = svc.check("key-1", "score", {"a": 1})
        assert result is None

    def test_start_and_check_returns_record(self, db: Session, settings: Settings) -> None:
        svc = IdempotencyService(db, settings)
        rec = svc.start("key-1", "score", {"a": 1})
        db.commit()
        assert rec.status == "processing"

        found = svc.check("key-1", "score", {"a": 1})
        assert found is not None
        assert found.idempotency_key == "key-1"

    def test_complete_stores_response(self, db: Session, settings: Settings) -> None:
        svc = IdempotencyService(db, settings)
        rec = svc.start("key-2", "score", {"x": 1})
        svc.complete(rec, 200, {"result": "ok"})
        db.commit()

        found = svc.check("key-2", "score", {"x": 1})
        assert found is not None
        assert found.status == "completed"
        assert found.response_status == 200
        assert found.response_body == {"result": "ok"}

    def test_duplicate_key_returns_cached(self, db: Session, settings: Settings) -> None:
        svc = IdempotencyService(db, settings)
        rec = svc.start("dup-1", "score", {"v": 1})
        svc.complete(rec, 200, {"score": 42})
        db.commit()

        found = svc.check("dup-1", "score", {"v": 1})
        assert found is not None
        assert found.response_body == {"score": 42}

    def test_expired_key_not_found(self, db: Session, settings: Settings) -> None:
        svc = IdempotencyService(db, settings)
        rec = svc.start("exp-1", "score", {"v": 1})
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        found = svc.check("exp-1", "score", {"v": 1})
        assert found is None

    def test_hash_consistency(self) -> None:
        h1 = IdempotencyService.compute_hash({"a": 1, "b": 2})
        h2 = IdempotencyService.compute_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_cleanup_expired(self, db: Session, settings: Settings) -> None:
        svc = IdempotencyService(db, settings)
        rec = svc.start("clean-1", "score", {})
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        count = svc.cleanup_expired()
        assert count == 1

    def test_fail_marks_record(self, db: Session, settings: Settings) -> None:
        svc = IdempotencyService(db, settings)
        rec = svc.start("fail-1", "score", {})
        svc.fail(rec, "something broke")
        db.commit()

        found = svc.check("fail-1", "score", {})
        assert found.status == "failed"


# ── Job Queue Tests ──────────────────────────────────────────────────


class TestJobQueue:
    def test_enqueue_creates_job(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        job = svc.enqueue("noop", {"test": True})
        db.commit()
        assert job.id is not None
        assert job.status == QUEUED
        assert job.attempts == 0

    def test_acquire_and_complete(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("noop")
        db.commit()

        job = svc.acquire_next()
        assert job is not None
        assert job.status == RUNNING
        assert job.attempts == 1

        svc.complete(job, {"done": True})
        db.commit()
        assert job.status == SUCCEEDED

    def test_fail_and_retry(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("noop", max_attempts=3)
        db.commit()

        job = svc.acquire_next()
        svc.fail(job, "error 1")
        db.commit()
        assert job.status == RETRYING
        assert job.attempts == 1

    def test_dead_after_max_attempts(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("noop", max_attempts=2)
        db.commit()

        job = svc.acquire_next()
        svc.fail(job, "err 1")
        db.commit()

        job.next_attempt_at = datetime.now(timezone.utc)
        db.commit()

        job = svc.acquire_next()
        assert job is not None
        svc.fail(job, "err 2")
        db.commit()
        assert job.status == DEAD

    def test_stale_lock_recovery(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("noop", max_attempts=3)
        db.commit()

        job = svc.acquire_next()
        assert job is not None
        job.leased_until = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        recovered = svc.recover_stale_locks()
        assert recovered == 1
        db.refresh(job)
        assert job.status == RETRYING
        assert job.locked_by is None

    def test_manual_retry(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("noop", max_attempts=1)
        db.commit()

        job = svc.acquire_next()
        svc.fail(job, "terminal")
        db.commit()
        assert job.status == DEAD

        retried = svc.retry_job(job.id)
        db.commit()
        assert retried is not None
        assert retried.status == RETRYING

    def test_requeue_all_failed(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        for i in range(3):
            j = svc.enqueue("noop", max_attempts=1)
            db.flush()
            j.status = DEAD
        db.commit()

        count = svc.requeue_all_failed()
        db.commit()
        assert count == 3

    def test_job_attempts_tracked(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("noop")
        db.commit()

        job = svc.acquire_next()
        svc.fail(job, "err")
        db.commit()

        attempts = svc.get_attempts(job.id)
        assert len(attempts) == 1
        assert attempts[0].status == "failed"

    def test_count_by_status(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("noop")
        svc.enqueue("noop")
        db.commit()

        counts = svc.count_by_status()
        assert counts.get("queued", 0) == 2

    def test_backoff_increases(self, settings: Settings) -> None:
        svc = JobService.__new__(JobService)
        svc.settings = settings
        b1 = svc._compute_backoff(1)
        b2 = svc._compute_backoff(2)
        b3 = svc._compute_backoff(3)
        assert b1 < b2 < b3

    def test_priority_ordering(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        low = svc.enqueue("noop", priority=0)
        high = svc.enqueue("noop", priority=10)
        db.commit()

        # High priority should be acquired first
        job = svc.acquire_next()
        assert job.id == high.id

    def test_retry_nonexistent_returns_none(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        assert svc.retry_job(99999) is None

    def test_list_jobs_with_filters(self, db: Session, settings: Settings) -> None:
        svc = JobService(db, settings)
        svc.enqueue("type_a")
        svc.enqueue("type_b")
        db.commit()

        a_jobs = svc.list_jobs(job_type="type_a")
        assert len(a_jobs) == 1


# ── Outbox Tests ─────────────────────────────────────────────────────


class TestOutbox:
    def test_publish_and_fetch(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        event = svc.publish("score.completed", "score", "req-1", {"score": 42})
        db.commit()
        assert event.status == "pending"
        assert event.dedup_key is not None

        pending = svc.fetch_pending()
        assert len(pending) == 1
        assert pending[0].id == event.id

    def test_dedup_prevents_duplicate(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        e1 = svc.publish("score.completed", "score", "req-1", {"score": 42})
        e2 = svc.publish("score.completed", "score", "req-1", {"score": 42})
        db.commit()
        assert e1.id == e2.id  # Same event returned

    def test_different_aggregates_not_deduped(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        e1 = svc.publish("score.completed", "score", "req-1", {})
        e2 = svc.publish("score.completed", "score", "req-2", {})
        db.commit()
        assert e1.id != e2.id

    def test_mark_dispatched(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        event = svc.publish("score.completed", "score", "req-2", {})
        db.commit()

        svc.mark_dispatched(event)
        db.commit()
        assert event.status == "dispatched"
        assert event.dispatched_at is not None

    def test_mark_failed_max_attempts(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        event = svc.publish("test", "test", "1", {})
        db.commit()

        for i in range(settings.outbox_max_dispatch_attempts):
            svc.mark_failed(event, f"error {i}")
        db.commit()
        assert event.status == "failed"

    def test_dispatch_single(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        event = svc.publish("test", "test", "1", {})
        event.status = "failed"
        db.commit()

        result = svc.dispatch_single(event.id)
        db.commit()
        assert result is not None
        assert result.status == "pending"

    def test_delivery_attempt_recorded(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        event = svc.publish("test", "test", "1", {})
        db.commit()

        attempt = svc.record_delivery_attempt(event, "webhook", "delivered", response_code=200)
        db.commit()
        assert attempt.id is not None
        assert attempt.status == "delivered"

    def test_count_pending(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        svc.publish("a", "a", "1", {})
        svc.publish("b", "b", "2", {})
        db.commit()
        assert svc.count_pending() == 2

    def test_count_failed(self, db: Session, settings: Settings) -> None:
        svc = OutboxService(db, settings)
        e = svc.publish("f", "f", "1", {})
        e.status = "failed"
        db.commit()
        assert svc.count_failed() == 1


# ── Failure / DLQ Tests ──────────────────────────────────────────────


class TestFailures:
    def test_record_failure(self, db: Session, settings: Settings) -> None:
        svc = FailureService(db, settings)
        rec = svc.record_failure("job", "123", "execute", "boom")
        db.commit()
        assert rec.id is not None

    def test_to_dead_letter(self, db: Session, settings: Settings) -> None:
        svc = FailureService(db, settings)
        item = svc.to_dead_letter(
            "outbox", "456", "dispatch", {"event": "data"}, "timeout"
        )
        db.commit()
        assert item.status == "failed"
        assert item.retry_count == 0

    def test_replay_dead_letter(self, db: Session, settings: Settings) -> None:
        svc = FailureService(db, settings)
        item = svc.to_dead_letter("job", "1", "exec", {}, "err")
        db.commit()

        replayed = svc.replay_dead_letter(item.id)
        db.commit()
        assert replayed is not None
        assert replayed.status == "retrying"
        assert replayed.retry_count == 1
        assert len(replayed.retry_history) == 1

    def test_list_dead_letter(self, db: Session, settings: Settings) -> None:
        svc = FailureService(db, settings)
        svc.to_dead_letter("job", "1", "exec", {}, "e1")
        svc.to_dead_letter("outbox", "2", "dispatch", {}, "e2")
        db.commit()

        items = svc.list_dead_letter()
        assert len(items) == 2

    def test_replay_nonexistent_returns_none(self, db: Session, settings: Settings) -> None:
        svc = FailureService(db, settings)
        assert svc.replay_dead_letter(99999) is None

    def test_count_by_status(self, db: Session, settings: Settings) -> None:
        svc = FailureService(db, settings)
        svc.to_dead_letter("a", "1", "op", {}, "e")
        svc.to_dead_letter("b", "2", "op", {}, "e")
        db.commit()
        counts = svc.count_by_status()
        assert counts.get("failed", 0) == 2


# ── Circuit Breaker Tests ────────────────────────────────────────────


class TestCircuitBreaker:
    def test_closed_by_default(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            try:
                cb.call(self._failing_fn)
            except ValueError:
                pass
        assert cb.state == CircuitState.OPEN

    def test_rejects_when_open(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        try:
            cb.call(self._failing_fn)
        except ValueError:
            pass
        with pytest.raises(CircuitBreakerError):
            cb.call(lambda: 42)

    def test_half_open_after_recovery(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
        try:
            cb.call(self._failing_fn)
        except ValueError:
            pass
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=1)
        try:
            cb.call(self._failing_fn)
        except ValueError:
            pass
        time.sleep(0.02)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_reset(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        try:
            cb.call(self._failing_fn)
        except ValueError:
            pass
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_registry(self) -> None:
        reg = CircuitBreakerRegistry(failure_threshold=5)
        cb1 = reg.get("webhook")
        cb2 = reg.get("webhook")
        assert cb1 is cb2
        assert len(reg.all_snapshots()) == 1

    def test_snapshot_content(self) -> None:
        cb = CircuitBreaker("snap", failure_threshold=5, recovery_timeout=30.0)
        snap = cb.snapshot()
        assert snap["name"] == "snap"
        assert snap["state"] == "closed"
        assert snap["failure_threshold"] == 5

    def test_reopens_on_half_open_failure(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=2)
        try:
            cb.call(self._failing_fn)
        except ValueError:
            pass
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        try:
            cb.call(self._failing_fn)
        except ValueError:
            pass
        assert cb.state == CircuitState.OPEN

    @staticmethod
    def _failing_fn():
        raise ValueError("fail")


# ── Source Protection Tests ──────────────────────────────────────────


class TestSourceProtection:
    def test_record_success(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        svc.record_success("src-a")
        db.commit()
        health = svc.get_health("src-a")
        assert health is not None
        assert health.total_requests == 1
        assert health.consecutive_failures == 0

    def test_auto_quarantine(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        for i in range(settings.source_quarantine_error_threshold):
            svc.record_failure("bad-src", f"error {i}")
        db.commit()
        assert svc.is_quarantined("bad-src")

    def test_manual_quarantine_and_resume(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        svc.quarantine("manual-src", "testing")
        db.commit()
        assert svc.is_quarantined("manual-src")

        svc.resume("manual-src")
        db.commit()
        assert not svc.is_quarantined("manual-src")

    def test_quarantine_expires(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        state = svc.quarantine("exp-src", "testing", duration_seconds=1)
        db.commit()
        state.quarantined_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        assert not svc.is_quarantined("exp-src")

    def test_summary(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        svc.record_success("good")
        svc.record_failure("bad", "err")
        db.commit()
        summary = svc.summary()
        assert summary["total_sources"] == 2

    def test_not_quarantined_by_default(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        assert not svc.is_quarantined("nonexistent")

    def test_success_resets_consecutive_failures(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        svc.record_failure("src-x", "e1")
        svc.record_failure("src-x", "e2")
        db.commit()
        h = svc.get_health("src-x")
        assert h.consecutive_failures == 2
        svc.record_success("src-x")
        db.commit()
        h = svc.get_health("src-x")
        assert h.consecutive_failures == 0

    def test_resume_nonexistent_returns_none(self, db: Session, settings: Settings) -> None:
        svc = SourceProtectionService(db, settings)
        assert svc.resume("ghost") is None


# ── Audit Tests ──────────────────────────────────────────────────────


class TestAudit:
    def test_log_entry(self, db: Session) -> None:
        svc = AuditService(db)
        entry = svc.log("admin", "job_retry", "job", "42", {"reason": "manual"})
        db.commit()
        assert entry.id is not None
        assert entry.action == "job_retry"

    def test_list_recent(self, db: Session) -> None:
        svc = AuditService(db)
        svc.log("admin", "a1", "job", "1")
        svc.log("admin", "a2", "source", "2")
        db.commit()
        entries = svc.list_recent()
        assert len(entries) == 2

    def test_list_filtered_by_action(self, db: Session) -> None:
        svc = AuditService(db)
        svc.log("admin", "retry", "job", "1")
        svc.log("admin", "quarantine", "source", "2")
        db.commit()
        entries = svc.list_recent(action="retry")
        assert len(entries) == 1
        assert entries[0].action == "retry"


# ── Security Tests ───────────────────────────────────────────────────


class TestSecurity:
    def test_redact_dict(self) -> None:
        data = {"username": "admin", "password": "s3cret", "token": "abc"}
        redacted = redact_dict(data)
        assert redacted["username"] == "admin"
        assert redacted["password"] == "***REDACTED***"
        assert redacted["token"] == "***REDACTED***"

    def test_redact_nested(self) -> None:
        data = {"config": {"api_key": "key123", "host": "localhost"}}
        redacted = redact_dict(data)
        assert redacted["config"]["api_key"] == "***REDACTED***"
        assert redacted["config"]["host"] == "localhost"

    def test_redact_preserves_non_dict(self) -> None:
        data = {"list_field": [1, 2, 3], "password": "secret"}
        redacted = redact_dict(data)
        assert redacted["list_field"] == [1, 2, 3]
        assert redacted["password"] == "***REDACTED***"


# ── Correlation ID Tests ─────────────────────────────────────────────


class TestCorrelation:
    def test_new_correlation_id(self) -> None:
        cid = new_correlation_id()
        assert len(cid) == 16
        assert get_correlation_id() == cid

    def test_set_correlation_id(self) -> None:
        set_correlation_id("test-cid-123")
        assert get_correlation_id() == "test-cid-123"


# ── Config Validation Tests ──────────────────────────────────────────


class TestConfig:
    def test_validate_prod_defaults(self) -> None:
        s = Settings(env="prod", database_url="postgresql+psycopg://x:x@localhost/db")
        errors = s.validate_config()
        assert any("ADMIN_API_KEY" in e for e in errors)

    def test_validate_ok_dev(self) -> None:
        s = Settings(env="dev", database_url="sqlite:///:memory:")
        errors = s.validate_config()
        assert len(errors) == 0

    def test_validate_bad_backoff(self) -> None:
        s = Settings(job_backoff_base_seconds=0.0)
        errors = s.validate_config()
        assert any("BACKOFF" in e for e in errors)

    def test_api_key_list_parsing(self) -> None:
        s = Settings(api_keys=" key1 , key2 , key3 ")
        assert s.api_key_list == ["key1", "key2", "key3"]


# ── API Integration Tests ────────────────────────────────────────────


class TestAPIIntegration:
    def test_health(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_score_backward_compatible(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.post(
            "/v1/score",
            json={"payload": {"amount": 100, "comment": "test"}, "request_id": "compat-1", "source": "test"},
            headers={"X-Api-Key": "dev-key-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["ok"] is True
        assert "review" in body

    def test_score_requires_auth(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.post("/v1/score", json={"payload": {"a": 1}, "request_id": "no-auth", "source": "t"})
        assert resp.status_code == 401

    def test_admin_requires_admin_key(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/v1/admin/jobs")
        assert resp.status_code == 403

    def test_admin_jobs_with_key(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/v1/admin/jobs", headers={"X-Admin-Key": "admin-secret-key"})
        assert resp.status_code == 200

    def test_admin_enqueue_job(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.post(
            "/v1/admin/jobs",
            json={"job_type": "noop", "payload": {"x": 1}},
            headers={"X-Admin-Key": "admin-secret-key"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "enqueued"

    def test_admin_job_not_found_404(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/v1/admin/jobs/999999", headers={"X-Admin-Key": "admin-secret-key"})
        assert resp.status_code == 404

    def test_admin_diagnostics(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/v1/admin/diagnostics/summary", headers={"X-Admin-Key": "admin-secret-key"})
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "recent_failures_24h" in body

    def test_admin_audit_log(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/v1/admin/audit", headers={"X-Admin-Key": "admin-secret-key"})
        assert resp.status_code == 200
        assert "entries" in resp.json()

    def test_admin_circuit_breakers(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/v1/admin/circuit-breakers", headers={"X-Admin-Key": "admin-secret-key"})
        assert resp.status_code == 200

    def test_admin_idempotency_cleanup(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.post("/v1/admin/idempotency/cleanup", headers={"X-Admin-Key": "admin-secret-key"})
        assert resp.status_code == 200

    def test_ready_endpoint_checks(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert "checks" in body

    def test_idempotent_score(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        headers = {"X-Api-Key": "dev-key-1", "Idempotency-Key": "idem-test-1"}
        payload = {"payload": {"amount": 50}, "request_id": "idem-r1", "source": "test"}

        resp1 = client.post("/v1/score", json=payload, headers=headers)
        assert resp1.status_code == 200

        resp2 = client.post("/v1/score", json=payload, headers=headers)
        assert resp2.status_code == 200

    def test_metrics_endpoint(self) -> None:
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert b"scoring" in resp.content

    def test_quarantine_blocks_scoring(self) -> None:
        """Quarantine a source, verify scoring is blocked, then resume."""
        from fastapi.testclient import TestClient
        from scoring_service.api.app import create_app
        client = TestClient(create_app())
        admin_h = {"X-Admin-Key": "admin-secret-key"}
        api_h = {"X-Api-Key": "dev-key-1"}

        # Quarantine
        resp = client.post("/v1/admin/sources/blocked-src/quarantine?reason=test", headers=admin_h)
        assert resp.status_code == 200

        # Try scoring from quarantined source
        resp = client.post(
            "/v1/score",
            json={"payload": {"a": 1}, "request_id": "q-1", "source": "blocked-src"},
            headers=api_h,
        )
        assert resp.status_code == 429

        # Resume
        resp = client.post("/v1/admin/sources/blocked-src/resume", headers=admin_h)
        assert resp.status_code == 200

        # Now scoring should work
        resp = client.post(
            "/v1/score",
            json={"payload": {"a": 1}, "request_id": "q-2", "source": "blocked-src"},
            headers=api_h,
        )
        assert resp.status_code == 200
