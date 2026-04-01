"""DB-backed job queue with retry, backoff, lease, and stale recovery."""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import JobAttempt, JobRecord

logger = logging.getLogger("scoring_service")

# Status constants
QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
RETRYING = "retrying"
DEAD = "dead"

TERMINAL_STATUSES = {SUCCEEDED, DEAD}
RETRYABLE_STATUSES = {QUEUED, RETRYING}


class JobService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.worker_id = uuid.uuid4().hex[:12]

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        max_attempts: int | None = None,
        priority: int = 0,
        correlation_id: str | None = None,
    ) -> JobRecord:
        now = datetime.now(timezone.utc)
        job = JobRecord(
            job_type=job_type,
            payload=payload or {},
            status=QUEUED,
            priority=priority,
            attempts=0,
            max_attempts=max_attempts or self.settings.job_max_attempts,
            next_attempt_at=now,
            correlation_id=correlation_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(job)
        self.db.flush()
        logger.info("job_enqueued job_id=%s type=%s", job.id, job_type)
        return job

    def acquire_next(self) -> JobRecord | None:
        """Acquire the next available job with lease."""
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=self.settings.job_lease_duration_seconds)

        job = (
            self.db.query(JobRecord)
            .filter(
                JobRecord.status.in_(RETRYABLE_STATUSES),
                or_(
                    JobRecord.next_attempt_at.is_(None),
                    JobRecord.next_attempt_at <= now,
                ),
                or_(
                    JobRecord.locked_by.is_(None),
                    JobRecord.leased_until < now,  # stale lock
                ),
            )
            .order_by(JobRecord.priority.desc(), JobRecord.next_attempt_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if job is None:
            return None

        job.status = RUNNING
        job.locked_by = self.worker_id
        job.leased_until = lease_until
        job.attempts += 1
        job.updated_at = now
        self.db.flush()

        # record attempt
        attempt = JobAttempt(
            job_id=job.id,
            attempt_number=job.attempts,
            status=RUNNING,
            started_at=now,
        )
        self.db.add(attempt)
        self.db.flush()

        logger.info(
            "job_acquired job_id=%s type=%s attempt=%s worker=%s",
            job.id, job.job_type, job.attempts, self.worker_id,
        )
        return job

    def complete(self, job: JobRecord, result: dict[str, Any] | None = None) -> None:
        now = datetime.now(timezone.utc)
        job.status = SUCCEEDED
        job.result = result
        job.locked_by = None
        job.leased_until = None
        job.updated_at = now
        self._finish_attempt(job.id, job.attempts, SUCCEEDED, now)
        self.db.flush()
        logger.info("job_completed job_id=%s type=%s", job.id, job.job_type)

    def fail(self, job: JobRecord, error: str) -> None:
        now = datetime.now(timezone.utc)
        job.last_error = error
        job.locked_by = None
        job.leased_until = None
        job.updated_at = now

        if job.attempts >= job.max_attempts:
            job.status = DEAD
            self._finish_attempt(job.id, job.attempts, FAILED, now, error)
            logger.warning(
                "job_dead job_id=%s type=%s attempts=%s error=%s",
                job.id, job.job_type, job.attempts, error[:200],
            )
        else:
            job.status = RETRYING
            backoff = self._compute_backoff(job.attempts)
            job.next_attempt_at = now + timedelta(seconds=backoff)
            self._finish_attempt(job.id, job.attempts, FAILED, now, error)
            logger.info(
                "job_retrying job_id=%s type=%s attempt=%s next_in=%.1fs",
                job.id, job.job_type, job.attempts, backoff,
            )
        self.db.flush()

    def _compute_backoff(self, attempt: int) -> float:
        base = self.settings.job_backoff_base_seconds
        cap = self.settings.job_backoff_max_seconds
        delay = min(base * (2 ** (attempt - 1)), cap)
        if self.settings.job_backoff_jitter:
            delay *= 0.5 + random.random() * 0.5  # noqa: S311
        return delay

    def _finish_attempt(
        self,
        job_id: int,
        attempt_number: int,
        status: str,
        finished_at: datetime,
        error: str | None = None,
    ) -> None:
        attempt = (
            self.db.query(JobAttempt)
            .filter(
                JobAttempt.job_id == job_id,
                JobAttempt.attempt_number == attempt_number,
            )
            .first()
        )
        if attempt:
            attempt.status = status
            attempt.error = error
            attempt.finished_at = finished_at

    def recover_stale_locks(self) -> int:
        """Recover jobs whose lease has expired (worker died)."""
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(
            seconds=self.settings.job_stale_lock_timeout_seconds
        )
        stale_jobs = (
            self.db.query(JobRecord)
            .filter(
                JobRecord.status == RUNNING,
                JobRecord.leased_until < stale_cutoff,
            )
            .all()
        )
        count = 0
        for job in stale_jobs:
            if job.attempts >= job.max_attempts:
                job.status = DEAD
                job.last_error = "stale lock recovery: max attempts exceeded"
            else:
                job.status = RETRYING
                job.next_attempt_at = now
            job.locked_by = None
            job.leased_until = None
            job.updated_at = now
            count += 1
            logger.warning("stale_job_recovered job_id=%s new_status=%s", job.id, job.status)
        if count:
            self.db.flush()
        return count

    def get_job(self, job_id: int) -> JobRecord | None:
        return self.db.query(JobRecord).filter(JobRecord.id == job_id).first()

    def list_jobs(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobRecord]:
        q = self.db.query(JobRecord)
        if status:
            q = q.filter(JobRecord.status == status)
        if job_type:
            q = q.filter(JobRecord.job_type == job_type)
        return q.order_by(JobRecord.created_at.desc()).offset(offset).limit(limit).all()

    def retry_job(self, job_id: int) -> JobRecord | None:
        """Manual retry: reset a dead/failed job."""
        job = self.get_job(job_id)
        if not job or job.status not in (DEAD, FAILED):
            return None
        now = datetime.now(timezone.utc)
        job.status = RETRYING
        job.next_attempt_at = now
        job.locked_by = None
        job.leased_until = None
        job.updated_at = now
        self.db.flush()
        logger.info("job_manual_retry job_id=%s", job_id)
        return job

    def requeue_all_failed(self) -> int:
        now = datetime.now(timezone.utc)
        dead_jobs = (
            self.db.query(JobRecord)
            .filter(JobRecord.status == DEAD)
            .all()
        )
        count = 0
        for job in dead_jobs:
            job.status = RETRYING
            job.next_attempt_at = now
            job.locked_by = None
            job.leased_until = None
            job.attempts = 0
            job.updated_at = now
            count += 1
        if count:
            self.db.flush()
        return count

    def get_attempts(self, job_id: int) -> list[JobAttempt]:
        return (
            self.db.query(JobAttempt)
            .filter(JobAttempt.job_id == job_id)
            .order_by(JobAttempt.attempt_number)
            .all()
        )

    def count_by_status(self) -> dict[str, int]:
        from sqlalchemy import func
        rows = (
            self.db.query(JobRecord.status, func.count())
            .group_by(JobRecord.status)
            .all()
        )
        return {status: cnt for status, cnt in rows}
