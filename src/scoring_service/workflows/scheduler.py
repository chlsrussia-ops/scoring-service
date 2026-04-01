"""Workflow scheduler — manages periodic/cron-based workflow execution."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import ScheduledJob
from scoring_service.workflows.engine import WorkflowEngine

logger = logging.getLogger("scoring_service")


class WorkflowScheduler:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.engine = WorkflowEngine(db, settings)

    def create_schedule(
        self, name: str, workflow_type: str, interval_seconds: int | None = None,
        cron_expression: str | None = None, tenant_id: str | None = None,
        config: dict | None = None,
    ) -> dict[str, Any]:
        existing = self.db.query(ScheduledJob).filter(ScheduledJob.name == name).first()
        if existing:
            return {"error": f"schedule '{name}' already exists", "id": existing.id}

        now = datetime.now(timezone.utc)
        next_run = now + timedelta(seconds=interval_seconds) if interval_seconds else now

        job = ScheduledJob(
            tenant_id=tenant_id, name=name, workflow_type=workflow_type,
            interval_seconds=interval_seconds, cron_expression=cron_expression,
            config_json=config or {}, next_run_at=next_run,
        )
        self.db.add(job)
        self.db.commit()
        return {"id": job.id, "name": name, "next_run_at": next_run.isoformat()}

    def tick(self) -> list[dict[str, Any]]:
        """Check for due schedules and execute them. Called by worker loop."""
        now = datetime.now(timezone.utc)
        due_jobs = (
            self.db.query(ScheduledJob)
            .filter(
                ScheduledJob.is_active == True,
                ScheduledJob.next_run_at <= now,
            )
            .all()
        )

        results = []
        for job in due_jobs:
            try:
                result = self.engine.start_workflow(
                    workflow_type=job.workflow_type,
                    input_data={"tenant_id": job.tenant_id},
                    tenant_id=job.tenant_id,
                    config=job.config_json,
                    triggered_by="schedule",
                )
                run_id = result.get("workflow_run_id")
                if run_id and not result.get("idempotent"):
                    self.db.flush()
                    exec_result = self.engine.execute_workflow(run_id)
                    job.last_run_id = run_id
                    job.last_status = exec_result.get("status", "unknown")
                    job.last_run_at = now
                    if exec_result.get("status") == "failed":
                        job.failure_count += 1
                    else:
                        job.failure_count = 0

                # Schedule next run
                if job.interval_seconds:
                    job.next_run_at = now + timedelta(seconds=job.interval_seconds)
                else:
                    job.next_run_at = now + timedelta(hours=6)  # default if no interval

                results.append({"schedule": job.name, "run_id": run_id, "status": job.last_status})
            except Exception as exc:
                logger.exception("scheduler_tick_failed schedule=%s", job.name)
                job.failure_count += 1
                job.last_status = "error"
                if job.interval_seconds:
                    job.next_run_at = now + timedelta(seconds=job.interval_seconds)
                results.append({"schedule": job.name, "error": str(exc)[:200]})

        self.db.commit()
        return results

    def list_schedules(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        q = self.db.query(ScheduledJob)
        if tenant_id:
            q = q.filter(ScheduledJob.tenant_id == tenant_id)
        jobs = q.order_by(ScheduledJob.name).all()
        return [
            {
                "id": j.id, "name": j.name, "workflow_type": j.workflow_type,
                "interval_seconds": j.interval_seconds, "is_active": j.is_active,
                "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
                "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
                "last_status": j.last_status, "failure_count": j.failure_count,
            }
            for j in jobs
        ]

    def toggle_schedule(self, schedule_id: int, active: bool) -> dict[str, Any]:
        job = self.db.get(ScheduledJob, schedule_id)
        if not job:
            return {"error": "not found"}
        job.is_active = active
        self.db.commit()
        return {"id": job.id, "is_active": job.is_active}
