"""Tests for Stage 5: Adaptation & Self-Improving System."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from scoring_service.config import Settings


@pytest.fixture
def settings():
    return Settings(
        database_url="sqlite:///:memory:",
        adaptation_enabled=True,
        adaptation_mode="auto_safe",
        adaptation_min_samples=5,
        source_learning_enabled=True,
        source_learning_min_samples=3,
        goal_optimization_enabled=True,
        experiment_enabled=True,
    )


@pytest.fixture
def db_session():
    """Create in-memory SQLite for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from scoring_service.db.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestFeedbackService:
    def test_record_feedback(self, db_session, settings):
        from scoring_service.adaptation.feedback_service import FeedbackService
        svc = FeedbackService(db_session, settings)
        fb = svc.record_feedback(
            tenant_id="test", target_type="trend", target_id=1,
            feedback_type="relevance", label="relevant",
            score=0.9, reviewer="tester",
        )
        assert fb.id is not None
        assert fb.label == "relevant"
        assert fb.tenant_id == "test"
        db_session.commit()

    def test_record_outcome(self, db_session, settings):
        from scoring_service.adaptation.feedback_service import FeedbackService
        svc = FeedbackService(db_session, settings)
        rec = svc.record_outcome(
            tenant_id="test", entity_type="alert", entity_id=1,
            outcome_type="true_positive", confidence=0.8,
        )
        assert rec.id is not None
        assert rec.outcome_type == "true_positive"
        db_session.commit()

    def test_list_feedback(self, db_session, settings):
        from scoring_service.adaptation.feedback_service import FeedbackService
        svc = FeedbackService(db_session, settings)
        for i in range(5):
            svc.record_feedback(
                tenant_id="test", target_type="trend", target_id=i,
                feedback_type="relevance", label="relevant",
            )
        db_session.commit()
        items = svc.list_feedback("test")
        assert len(items) == 5


class TestEvaluationService:
    def test_run_evaluation(self, db_session, settings):
        from scoring_service.adaptation.feedback_service import FeedbackService
        from scoring_service.adaptation.evaluation_service import EvaluationService

        # Seed some feedback and outcomes
        fb_svc = FeedbackService(db_session, settings)
        for i in range(15):
            fb_svc.record_feedback(
                tenant_id="test", target_type="recommendation", target_id=i,
                feedback_type="usefulness", label="useful" if i % 3 != 0 else "useless",
            )
            fb_svc.record_outcome(
                tenant_id="test", entity_type="alert", entity_id=i,
                outcome_type="true_positive" if i % 4 != 0 else "false_positive",
                evidence={"source": "rss"},
            )
            fb_svc.record_outcome(
                tenant_id="test", entity_type="trend", entity_id=i,
                outcome_type="confirmed" if i % 3 != 0 else "rejected",
                evidence={"source": "rss"},
            )
        db_session.commit()

        eval_svc = EvaluationService(db_session, settings)
        result = eval_svc.run_evaluation("test", "7d")
        assert result["evaluation_run_id"] is not None
        assert "metrics" in result

    def test_get_scorecard_empty(self, db_session, settings):
        from scoring_service.adaptation.evaluation_service import EvaluationService
        svc = EvaluationService(db_session, settings)
        card = svc.get_scorecard("test", "7d")
        assert "message" in card or "metrics" in card


class TestPolicyTuningService:
    def test_create_and_approve_proposal(self, db_session, settings):
        from scoring_service.adaptation.repository import AdaptationRepository
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService

        repo = AdaptationRepository(db_session)
        proposal = repo.create_proposal(
            tenant_id="test", proposal_type="threshold",
            target_type="policy", target_id="alert_threshold",
            current_value_json={"val": 50}, proposed_value_json={"val": 55},
            delta_json={"delta": 5}, reason="test proposal", risk_level="safe",
        )
        db_session.commit()

        svc = PolicyTuningService(db_session, settings)
        result = svc.approve_proposal(proposal.id, "tester")
        assert result["status"] == "approved"
        db_session.commit()

    def test_apply_proposal_creates_profile(self, db_session, settings):
        from scoring_service.adaptation.repository import AdaptationRepository
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService

        repo = AdaptationRepository(db_session)
        proposal = repo.create_proposal(
            tenant_id="test", proposal_type="source_trust",
            target_type="source", target_id="rss",
            current_value_json={"trust_score": 1.0},
            proposed_value_json={"trust_score": 0.9},
            delta_json={"trust_delta": -0.1}, reason="noisy source",
            risk_level="safe",
        )
        proposal.status = "approved"
        db_session.commit()

        svc = PolicyTuningService(db_session, settings)
        result = svc.apply_proposal(proposal.id)
        assert result["status"] == "applied"
        assert result["new_version"] == 2
        db_session.commit()

    def test_simulate_proposal(self, db_session, settings):
        from scoring_service.adaptation.repository import AdaptationRepository
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService

        repo = AdaptationRepository(db_session)
        proposal = repo.create_proposal(
            tenant_id="test", proposal_type="weight",
            target_type="scoring_profile", target_id="weights",
            current_value_json={"weight": 1.0},
            proposed_value_json={"weight": 1.15},
            delta_json={"delta": 0.15}, reason="test",
            risk_level="safe",
        )
        db_session.commit()

        svc = PolicyTuningService(db_session, settings)
        result = svc.simulate_proposal(proposal.id)
        assert result["dry_run"] is True


class TestRollbackService:
    def test_rollback_applied_proposal(self, db_session, settings):
        from scoring_service.adaptation.repository import AdaptationRepository
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService
        from scoring_service.adaptation.rollback_service import RollbackService

        repo = AdaptationRepository(db_session)
        # Create profile first
        profile = repo.create_profile(
            tenant_id="test", name="default", is_active=True,
            weights_json={"original": 1.0},
        )
        db_session.flush()

        # Create and apply proposal
        proposal = repo.create_proposal(
            tenant_id="test", proposal_type="weight",
            target_type="scoring_profile", target_id="weights",
            current_value_json={"weight": 1.0},
            proposed_value_json={"confidence_weight_boost": 0.15},
            delta_json={"delta": 0.15}, reason="test", risk_level="safe",
        )
        proposal.status = "approved"
        db_session.commit()

        tuning = PolicyTuningService(db_session, settings)
        tuning.apply_proposal(proposal.id)
        db_session.commit()

        # Rollback
        rollback_svc = RollbackService(db_session, settings)
        result = rollback_svc.rollback_proposal(proposal.id, "test rollback")
        assert result["status"] == "rolled_back"
        db_session.commit()


class TestSourceLearningService:
    def test_update_source_trust(self, db_session, settings):
        from scoring_service.adaptation.feedback_service import FeedbackService
        from scoring_service.adaptation.source_learning_service import SourceLearningService

        fb_svc = FeedbackService(db_session, settings)
        for i in range(10):
            fb_svc.record_outcome(
                tenant_id="test", entity_type="trend", entity_id=i,
                outcome_type="confirmed" if i % 3 != 0 else "rejected",
                evidence={"source": "rss"},
            )
        db_session.commit()

        src_svc = SourceLearningService(db_session, settings)
        updates = src_svc.update_source_trust("test")
        # May or may not have updates depending on sample thresholds
        assert isinstance(updates, list)

    def test_get_summary(self, db_session, settings):
        from scoring_service.adaptation.source_learning_service import SourceLearningService
        svc = SourceLearningService(db_session, settings)
        summary = svc.get_summary("test")
        assert "total_sources" in summary


class TestGoalService:
    def test_create_and_list_goals(self, db_session, settings):
        from scoring_service.adaptation.goal_service import GoalOptimizationService
        svc = GoalOptimizationService(db_session, settings)
        goal = svc.create_goal(
            tenant_id="test", name="Maximize precision",
            target_metric="alert_precision", direction="maximize",
            target_value=0.9, guardrails_json={},
        )
        db_session.commit()
        assert goal.id is not None
        goals = svc.list_goals("test")
        assert len(goals) >= 1


class TestExperimentService:
    def test_create_experiment(self, db_session, settings):
        from scoring_service.adaptation.experiment_service import ExperimentService
        svc = ExperimentService(db_session, settings)
        exp = svc.create_experiment(
            tenant_id="test", name="Test experiment",
            experiment_type="replay",
        )
        assert exp.id is not None
        assert exp.experiment_type == "replay"
        db_session.commit()


class TestOrchestrator:
    def test_get_status(self, db_session, settings):
        from scoring_service.adaptation.orchestrator import AdaptationOrchestrator
        orch = AdaptationOrchestrator(db_session, settings)
        status = orch.get_status("test")
        assert "mode" in status
        assert "enabled" in status
        assert status["enabled"] is True


class TestAdaptiveScoringService:
    def test_adjust_score_no_profile(self, db_session, settings):
        from scoring_service.adaptation.adaptive_scoring_service import AdaptiveScoringService
        svc = AdaptiveScoringService(db_session, settings)
        result = svc.adjust_score("test", "trend", 1, 75.0)
        assert result["base_score"] == 75.0
        assert result["adjusted_score"] == 75.0

    def test_adjust_score_with_profile(self, db_session, settings):
        from scoring_service.adaptation.adaptive_scoring_service import AdaptiveScoringService
        from scoring_service.adaptation.repository import AdaptationRepository

        repo = AdaptationRepository(db_session)
        repo.create_profile(
            tenant_id="test", name="default", is_active=True,
            source_trust_json={"rss": 1.2},
            category_trust_json={"tech": 0.8},
        )
        db_session.commit()

        svc = AdaptiveScoringService(db_session, settings)
        result = svc.adjust_score("test", "trend", 1, 75.0, source="rss", category="tech")
        assert result["adjusted_score"] != 75.0
        assert "source_trust" in result["adjustments"]


class TestGuardrails:
    def test_mode_observe_only_blocks_apply(self, db_session, settings):
        settings.adaptation_mode = "observe_only"
        from scoring_service.adaptation.repository import AdaptationRepository
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService

        repo = AdaptationRepository(db_session)
        proposal = repo.create_proposal(
            tenant_id="test", proposal_type="threshold",
            target_type="policy", target_id="alert",
            current_value_json={}, proposed_value_json={},
            delta_json={}, reason="test", risk_level="safe",
        )
        db_session.commit()

        svc = PolicyTuningService(db_session, settings)
        result = svc.apply_proposal(proposal.id)
        assert "error" in result

    def test_suggest_only_blocks_pending(self, db_session, settings):
        settings.adaptation_mode = "suggest_only"
        from scoring_service.adaptation.repository import AdaptationRepository
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService

        repo = AdaptationRepository(db_session)
        proposal = repo.create_proposal(
            tenant_id="test", proposal_type="threshold",
            target_type="policy", target_id="alert",
            current_value_json={}, proposed_value_json={},
            delta_json={}, reason="test", risk_level="safe",
        )
        db_session.commit()

        svc = PolicyTuningService(db_session, settings)
        result = svc.apply_proposal(proposal.id)
        assert "error" in result
        assert "approve" in result["error"]

    def test_risky_proposal_needs_approval(self, db_session, settings):
        settings.adaptation_mode = "auto_safe"
        from scoring_service.adaptation.repository import AdaptationRepository
        from scoring_service.adaptation.policy_tuning_service import PolicyTuningService

        repo = AdaptationRepository(db_session)
        proposal = repo.create_proposal(
            tenant_id="test", proposal_type="threshold",
            target_type="policy", target_id="alert",
            current_value_json={}, proposed_value_json={},
            delta_json={}, reason="test", risk_level="risky",
        )
        db_session.commit()

        svc = PolicyTuningService(db_session, settings)
        result = svc.apply_proposal(proposal.id)
        assert "error" in result
        assert "approval" in result["error"]


class TestContracts:
    def test_feedback_create_validation(self):
        from scoring_service.adaptation_contracts import FeedbackCreate
        fb = FeedbackCreate(
            target_type="trend", target_id=1,
            feedback_type="relevance", label="relevant",
        )
        assert fb.target_type == "trend"

    def test_feedback_create_invalid_type(self):
        from scoring_service.adaptation_contracts import FeedbackCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FeedbackCreate(
                target_type="invalid_type", target_id=1,
                feedback_type="relevance", label="relevant",
            )

    def test_goal_create(self):
        from scoring_service.adaptation_contracts import GoalCreate
        goal = GoalCreate(
            name="test", target_metric="precision",
            direction="maximize", target_value=0.9,
        )
        assert goal.direction == "maximize"

    def test_outcome_create(self):
        from scoring_service.adaptation_contracts import OutcomeCreate
        outcome = OutcomeCreate(
            entity_type="alert", entity_id=1,
            outcome_type="true_positive",
        )
        assert outcome.confidence == 0.5
