"""Workflow execution engine — orchestrates multi-step async processes."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import WorkflowRun, WorkflowStep

logger = logging.getLogger("scoring_service")

# ── Workflow Definition Registry ─────────────────────────────────────

StepFn = Callable[[dict, dict, Session, Settings], dict]

_WORKFLOW_REGISTRY: dict[str, "WorkflowDefinition"] = {}


class WorkflowDefinition:
    """Declares a workflow with ordered steps."""

    def __init__(self, workflow_type: str, steps: list[tuple[str, StepFn, bool, int]]):
        """
        steps: list of (step_name, handler_fn, is_retryable, max_attempts)
        """
        self.workflow_type = workflow_type
        self.steps = steps

    def register(self) -> "WorkflowDefinition":
        _WORKFLOW_REGISTRY[self.workflow_type] = self
        return self


def get_workflow_definition(workflow_type: str) -> WorkflowDefinition | None:
    return _WORKFLOW_REGISTRY.get(workflow_type)


def list_workflow_types() -> list[str]:
    return list(_WORKFLOW_REGISTRY.keys())


# ── Workflow Engine ──────────────────────────────────────────────────

class WorkflowEngine:
    """Executes workflows with retry safety, idempotency, and step tracking."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def start_workflow(
        self, workflow_type: str, input_data: dict | None = None,
        tenant_id: str | None = None, config: dict | None = None,
        idempotency_key: str | None = None, triggered_by: str = "api",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a new workflow run."""
        definition = get_workflow_definition(workflow_type)
        if not definition:
            return {"error": f"unknown workflow type: {workflow_type}"}

        # Idempotency check
        if idempotency_key:
            existing = (
                self.db.query(WorkflowRun)
                .filter(WorkflowRun.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return {
                    "workflow_run_id": existing.id, "status": existing.status,
                    "idempotent": True, "message": "workflow already exists",
                }

        run = WorkflowRun(
            tenant_id=tenant_id, workflow_type=workflow_type,
            idempotency_key=idempotency_key,
            config_json=config or {}, input_json=input_data or {},
            total_steps=len(definition.steps),
            triggered_by=triggered_by,
            correlation_id=correlation_id or uuid.uuid4().hex[:16],
            status="pending",
        )
        self.db.add(run)
        self.db.flush()

        # Create step records
        for i, (step_name, _, is_retryable, max_attempts) in enumerate(definition.steps):
            step = WorkflowStep(
                workflow_run_id=run.id, step_name=step_name,
                step_order=i, is_retryable=is_retryable,
                max_attempts=max_attempts,
            )
            self.db.add(step)
        self.db.flush()

        logger.info(
            "workflow_created run_id=%d type=%s steps=%d tenant=%s",
            run.id, workflow_type, len(definition.steps), tenant_id,
        )
        return {"workflow_run_id": run.id, "status": "pending", "steps": len(definition.steps)}

    def execute_workflow(self, run_id: int) -> dict[str, Any]:
        """Execute all pending steps of a workflow synchronously."""
        run = self.db.get(WorkflowRun, run_id)
        if not run:
            return {"error": "workflow run not found"}
        if run.status in ("completed", "cancelled"):
            return {"workflow_run_id": run.id, "status": run.status, "message": "already terminal"}

        definition = get_workflow_definition(run.workflow_type)
        if not definition:
            run.status = "failed"
            run.error_message = f"workflow definition not found: {run.workflow_type}"
            self.db.commit()
            return {"error": run.error_message}

        run.status = "running"
        run.started_at = run.started_at or datetime.now(timezone.utc)
        self.db.flush()

        steps = (
            self.db.query(WorkflowStep)
            .filter(WorkflowStep.workflow_run_id == run_id)
            .order_by(WorkflowStep.step_order)
            .all()
        )

        step_context = dict(run.input_json)

        for step_record in steps:
            if step_record.status == "completed":
                # Already done, carry forward output
                if step_record.output_json:
                    step_context.update(step_record.output_json)
                continue
            if step_record.status == "skipped":
                continue

            run.current_step = step_record.step_name
            self.db.flush()

            # Find handler
            handler = None
            for name, fn, _, _ in definition.steps:
                if name == step_record.step_name:
                    handler = fn
                    break

            if not handler:
                step_record.status = "failed"
                step_record.error_message = f"handler not found for step: {step_record.step_name}"
                run.status = "failed"
                run.error_message = step_record.error_message
                self.db.commit()
                return {"error": step_record.error_message}

            # Execute with retry
            result = self._execute_step(step_record, handler, step_context, run)
            if result.get("failed"):
                run.status = "failed"
                run.error_message = result.get("error", "step failed")
                run.completed_at = datetime.now(timezone.utc)
                self.db.commit()
                return {"workflow_run_id": run.id, "status": "failed", "failed_step": step_record.step_name, "error": run.error_message}

            # Carry forward
            if step_record.output_json:
                step_context.update(step_record.output_json)
            run.completed_steps += 1
            self.db.flush()

        # All done
        run.status = "completed"
        run.output_json = step_context
        run.completed_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info("workflow_completed run_id=%d type=%s", run.id, run.workflow_type)
        return {"workflow_run_id": run.id, "status": "completed", "output": step_context}

    def _execute_step(
        self, step: WorkflowStep, handler: StepFn, context: dict, run: WorkflowRun,
    ) -> dict[str, Any]:
        """Execute a single step with retry logic."""
        while step.attempts < step.max_attempts:
            step.attempts += 1
            step.status = "running"
            step.started_at = step.started_at or datetime.now(timezone.utc)
            self.db.flush()

            try:
                output = handler(context, run.config_json, self.db, self.settings)
                step.status = "completed"
                step.output_json = output or {}
                step.completed_at = datetime.now(timezone.utc)
                self.db.flush()
                return {"success": True}
            except Exception as exc:
                error_msg = str(exc)[:500]
                step.error_message = error_msg
                logger.warning(
                    "workflow_step_failed run_id=%d step=%s attempt=%d/%d error=%s",
                    run.id, step.step_name, step.attempts, step.max_attempts, error_msg[:200],
                )
                if step.attempts >= step.max_attempts or not step.is_retryable:
                    step.status = "failed"
                    self.db.flush()
                    return {"failed": True, "error": error_msg}
                # Backoff before retry
                time.sleep(min(0.5 * (2 ** (step.attempts - 1)), 5))

        step.status = "failed"
        self.db.flush()
        return {"failed": True, "error": step.error_message or "max attempts reached"}

    def get_status(self, run_id: int) -> dict[str, Any]:
        run = self.db.get(WorkflowRun, run_id)
        if not run:
            return {"error": "not found"}
        steps = (
            self.db.query(WorkflowStep)
            .filter(WorkflowStep.workflow_run_id == run_id)
            .order_by(WorkflowStep.step_order)
            .all()
        )
        return {
            "workflow_run_id": run.id, "type": run.workflow_type,
            "status": run.status, "current_step": run.current_step,
            "progress": f"{run.completed_steps}/{run.total_steps}",
            "triggered_by": run.triggered_by,
            "correlation_id": run.correlation_id,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error": run.error_message,
            "steps": [
                {
                    "name": s.step_name, "status": s.status,
                    "attempts": s.attempts, "max_attempts": s.max_attempts,
                    "error": s.error_message,
                }
                for s in steps
            ],
        }

    def cancel_workflow(self, run_id: int) -> dict[str, Any]:
        run = self.db.get(WorkflowRun, run_id)
        if not run:
            return {"error": "not found"}
        if run.status in ("completed", "cancelled"):
            return {"error": f"already {run.status}"}
        run.status = "cancelled"
        run.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"workflow_run_id": run.id, "status": "cancelled"}

    def retry_workflow(self, run_id: int) -> dict[str, Any]:
        run = self.db.get(WorkflowRun, run_id)
        if not run:
            return {"error": "not found"}
        if run.status != "failed":
            return {"error": f"can only retry failed workflows, current: {run.status}"}
        # Reset failed steps
        steps = (
            self.db.query(WorkflowStep)
            .filter(WorkflowStep.workflow_run_id == run_id, WorkflowStep.status == "failed")
            .all()
        )
        for s in steps:
            s.status = "pending"
            s.attempts = 0
            s.error_message = None
        run.status = "pending"
        run.error_message = None
        self.db.commit()
        return self.execute_workflow(run_id)

    def list_runs(
        self, tenant_id: str | None = None, status: str | None = None,
        workflow_type: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        q = self.db.query(WorkflowRun)
        if tenant_id:
            q = q.filter(WorkflowRun.tenant_id == tenant_id)
        if status:
            q = q.filter(WorkflowRun.status == status)
        if workflow_type:
            q = q.filter(WorkflowRun.workflow_type == workflow_type)
        runs = q.order_by(WorkflowRun.created_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id, "type": r.workflow_type, "status": r.status,
                "progress": f"{r.completed_steps}/{r.total_steps}",
                "triggered_by": r.triggered_by,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]
