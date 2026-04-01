"""Tests for Workflow Orchestration."""
from __future__ import annotations
import pytest
from scoring_service.config import Settings


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from scoring_service.db.models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def settings():
    return Settings(database_url="sqlite:///:memory:", adaptation_enabled=True)


@pytest.fixture(autouse=True)
def register_workflows():
    from scoring_service.workflows.definitions import register_builtin_workflows
    register_builtin_workflows()


class TestWorkflowEngine:
    def test_start_workflow(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine
        engine = WorkflowEngine(db_session, settings)
        result = engine.start_workflow("test_workflow", input_data={"key": "val"})
        assert result["workflow_run_id"] is not None
        assert result["steps"] == 2
        db_session.commit()

    def test_execute_workflow(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine
        engine = WorkflowEngine(db_session, settings)
        start = engine.start_workflow("test_workflow")
        db_session.commit()
        result = engine.execute_workflow(start["workflow_run_id"])
        assert result["status"] == "completed"

    def test_idempotency(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine
        engine = WorkflowEngine(db_session, settings)
        r1 = engine.start_workflow("test_workflow", idempotency_key="test-key-1")
        db_session.commit()
        r2 = engine.start_workflow("test_workflow", idempotency_key="test-key-1")
        assert r2.get("idempotent") is True
        assert r1["workflow_run_id"] == r2["workflow_run_id"]

    def test_get_status(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine
        engine = WorkflowEngine(db_session, settings)
        start = engine.start_workflow("test_workflow")
        db_session.commit()
        status = engine.get_status(start["workflow_run_id"])
        assert status["type"] == "test_workflow"
        assert len(status["steps"]) == 2

    def test_cancel_workflow(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine
        engine = WorkflowEngine(db_session, settings)
        start = engine.start_workflow("test_workflow")
        db_session.commit()
        result = engine.cancel_workflow(start["workflow_run_id"])
        assert result["status"] == "cancelled"

    def test_unknown_workflow_type(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine
        engine = WorkflowEngine(db_session, settings)
        result = engine.start_workflow("nonexistent_type")
        assert "error" in result

    def test_list_runs(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine
        engine = WorkflowEngine(db_session, settings)
        engine.start_workflow("test_workflow", tenant_id="t1")
        engine.start_workflow("test_workflow", tenant_id="t1")
        db_session.commit()
        runs = engine.list_runs(tenant_id="t1")
        assert len(runs) == 2

    def test_retry_failed_workflow(self, db_session, settings):
        from scoring_service.workflows.engine import WorkflowEngine, WorkflowDefinition

        def failing_step(ctx, config, db, s):
            if ctx.get("_fail_count", 0) < 1:
                ctx["_fail_count"] = ctx.get("_fail_count", 0) + 1
                raise ValueError("transient error")
            return {"recovered": True}

        WorkflowDefinition("retry_test", [
            ("fail_step", failing_step, True, 3),
        ]).register()

        engine = WorkflowEngine(db_session, settings)
        start = engine.start_workflow("retry_test")
        db_session.commit()
        result = engine.execute_workflow(start["workflow_run_id"])
        # Should complete because retry succeeds on 2nd attempt
        assert result["status"] == "completed"


class TestWorkflowScheduler:
    def test_create_schedule(self, db_session, settings):
        from scoring_service.workflows.scheduler import WorkflowScheduler
        sched = WorkflowScheduler(db_session, settings)
        result = sched.create_schedule(
            name="test-schedule", workflow_type="test_workflow",
            interval_seconds=3600,
        )
        assert result["id"] is not None

    def test_duplicate_schedule(self, db_session, settings):
        from scoring_service.workflows.scheduler import WorkflowScheduler
        sched = WorkflowScheduler(db_session, settings)
        sched.create_schedule(name="dup-test", workflow_type="test_workflow", interval_seconds=600)
        result = sched.create_schedule(name="dup-test", workflow_type="test_workflow", interval_seconds=600)
        assert "error" in result

    def test_list_schedules(self, db_session, settings):
        from scoring_service.workflows.scheduler import WorkflowScheduler
        sched = WorkflowScheduler(db_session, settings)
        sched.create_schedule(name="sched1", workflow_type="test_workflow", interval_seconds=600)
        schedules = sched.list_schedules()
        assert len(schedules) >= 1

    def test_toggle_schedule(self, db_session, settings):
        from scoring_service.workflows.scheduler import WorkflowScheduler
        sched = WorkflowScheduler(db_session, settings)
        result = sched.create_schedule(name="toggle-test", workflow_type="test_workflow", interval_seconds=600)
        toggle = sched.toggle_schedule(result["id"], False)
        assert toggle["is_active"] is False


class TestWorkflowDefinitions:
    def test_builtin_workflows_registered(self):
        from scoring_service.workflows.engine import list_workflow_types
        types = list_workflow_types()
        assert "adaptation_cycle" in types
        assert "benchmark_run" in types
        assert "test_workflow" in types
