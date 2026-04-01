"""Tests for Data Contracts & Schema Governance."""
from __future__ import annotations
import pytest

from scoring_service.contracts_registry.registry import ContractRegistry, Compatibility
from scoring_service.contracts_registry.domain_contracts import (
    ScoreCompletedEventV1, ScoreCompletedEventV2,
    FeedbackEventContractV1, BenchmarkResultContractV1,
    WorkflowCompletedContractV1, TrendDetectedContractV1,
    register_all_contracts,
)


@pytest.fixture
def registry():
    return ContractRegistry()


class TestContractRegistry:
    def test_register_and_get(self, registry):
        registry.register("test.event", 1, ScoreCompletedEventV1, "test", "test event")
        result = registry.get("test.event", 1)
        assert result is not None
        schema, meta = result
        assert meta.name == "test.event"
        assert meta.version == 1

    def test_get_latest_version(self, registry):
        registry.register("test.event", 1, ScoreCompletedEventV1, "test")
        registry.register("test.event", 2, ScoreCompletedEventV2, "test")
        result = registry.get("test.event")
        assert result is not None
        _, meta = result
        assert meta.version == 2

    def test_get_nonexistent(self, registry):
        result = registry.get("nonexistent")
        assert result is None

    def test_list_contracts(self, registry):
        registry.register("a.event", 1, ScoreCompletedEventV1, "scoring")
        registry.register("b.event", 1, FeedbackEventContractV1, "adaptation")
        all_contracts = registry.list_contracts()
        assert len(all_contracts) == 2
        scoring_only = registry.list_contracts(domain="scoring")
        assert len(scoring_only) == 1

    def test_list_versions(self, registry):
        registry.register("versioned", 1, ScoreCompletedEventV1, "test")
        registry.register("versioned", 2, ScoreCompletedEventV2, "test")
        versions = registry.list_versions("versioned")
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2


class TestValidation:
    def test_valid_payload(self, registry):
        registry.register("score.completed", 1, ScoreCompletedEventV1, "scoring")
        result = registry.validate("score.completed", {
            "request_id": "r1", "source": "test", "score": 85.0,
            "review_label": "excellent", "approved": True,
        }, version=1)
        assert result["valid"] is True

    def test_invalid_payload(self, registry):
        registry.register("score.completed", 1, ScoreCompletedEventV1, "scoring")
        result = registry.validate("score.completed", {"bad": "data"}, version=1)
        assert result["valid"] is False

    def test_extra_fields_rejected(self, registry):
        registry.register("score.completed", 1, ScoreCompletedEventV1, "scoring")
        result = registry.validate("score.completed", {
            "request_id": "r1", "source": "test", "score": 85.0,
            "review_label": "excellent", "approved": True,
            "unknown_field": "should_fail",
        }, version=1)
        assert result["valid"] is False

    def test_validate_nonexistent(self, registry):
        result = registry.validate("nonexistent", {})
        assert result["valid"] is False


class TestCompatibility:
    def test_backward_compatible(self, registry):
        registry.register("test", 1, ScoreCompletedEventV1, "test")
        registry.register("test", 2, ScoreCompletedEventV2, "test")
        result = registry.check_compatibility("test", 1, 2)
        assert result["compatible"] is True
        assert "tenant_id" in result["added_fields"]
        assert len(result["removed_fields"]) == 0

    def test_same_schema(self, registry):
        registry.register("test", 1, ScoreCompletedEventV1, "test")
        registry.register("test", 2, ScoreCompletedEventV1, "test")
        result = registry.check_compatibility("test", 1, 2)
        assert result["same_schema"] is True
        assert result["compatible"] is True

    def test_schema_hash_differs(self, registry):
        registry.register("test", 1, ScoreCompletedEventV1, "test")
        registry.register("test", 2, ScoreCompletedEventV2, "test")
        result = registry.check_compatibility("test", 1, 2)
        assert result["same_schema"] is False


class TestDeprecation:
    def test_deprecate_contract(self, registry):
        registry.register("old.event", 1, ScoreCompletedEventV1, "test")
        success = registry.deprecate("old.event", 1, "new.event:v1")
        assert success is True
        _, meta = registry.get("old.event", 1)
        assert meta.status.value == "deprecated"
        assert meta.deprecated_by == "new.event:v1"


class TestDomainContracts:
    def test_register_all(self):
        count = register_all_contracts()
        assert count >= 12

    def test_score_completed_v1(self):
        event = ScoreCompletedEventV1(
            request_id="r1", source="test", score=85.0,
            review_label="excellent", approved=True,
        )
        assert event.score == 85.0

    def test_score_completed_v2_backward_compatible(self):
        # V2 should accept V1 data (missing optional fields)
        event = ScoreCompletedEventV2(
            request_id="r1", source="test", score=85.0,
            review_label="excellent", approved=True,
        )
        assert event.tenant_id is None
        assert event.breakdown == {}

    def test_feedback_contract(self):
        fb = FeedbackEventContractV1(
            target_type="trend", target_id=1,
            feedback_type="relevance", label="relevant",
        )
        assert fb.source == "human"

    def test_trend_detected(self):
        t = TrendDetectedContractV1(
            trend_id=1, tenant_id="demo", source="rss",
            category="tech", topic="AI", score=85.0,
            confidence=0.9, direction="rising", event_count=10,
        )
        assert t.direction == "rising"

    def test_workflow_completed(self):
        w = WorkflowCompletedContractV1(
            workflow_run_id=1, workflow_type="adaptation_cycle",
            status="completed", completed_steps=5, total_steps=5,
            triggered_by="schedule",
        )
        assert w.status == "completed"

    def test_benchmark_result(self):
        b = BenchmarkResultContractV1(
            run_id=1, dataset_id=1, strategy_name="default",
            strategy_version="v1", status="completed",
            item_count=100, metrics={"precision@5": 0.8},
        )
        assert b.metrics["precision@5"] == 0.8
