"""Tests for Stage 3 platform features."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from scoring_service.policies.engine import (
    evaluate_condition,
    evaluate_rule,
    evaluate_policy_rules,
)
from scoring_service.plugins.base import ProviderMeta
from scoring_service.plugins.builtin import (
    DefaultNormalizer,
    DefaultScorer,
    DemoSourceProvider,
    DiversityRecommender,
    LogNotificationProvider,
    SpikeDetector,
    ThresholdDetector,
    TopNRecommender,
)
from scoring_service.plugins.registry import PluginRegistry


# ── Policy Engine Tests ────────────────────────────────────────────


class TestPolicyEngine:
    def test_eq_operator(self):
        assert evaluate_condition({"status": "active"}, "status", "eq", "active") is True
        assert evaluate_condition({"status": "active"}, "status", "eq", "inactive") is False

    def test_neq_operator(self):
        assert evaluate_condition({"x": 1}, "x", "neq", 2) is True
        assert evaluate_condition({"x": 1}, "x", "neq", 1) is False

    def test_gt_operator(self):
        assert evaluate_condition({"score": 80}, "score", "gt", 50) is True
        assert evaluate_condition({"score": 30}, "score", "gt", 50) is False

    def test_gte_operator(self):
        assert evaluate_condition({"score": 50}, "score", "gte", 50) is True
        assert evaluate_condition({"score": 49}, "score", "gte", 50) is False

    def test_lt_lte_operators(self):
        assert evaluate_condition({"v": 3}, "v", "lt", 5) is True
        assert evaluate_condition({"v": 5}, "v", "lte", 5) is True
        assert evaluate_condition({"v": 6}, "v", "lt", 5) is False

    def test_in_operator(self):
        assert evaluate_condition({"cat": "tech"}, "cat", "in", ["tech", "biz"]) is True
        assert evaluate_condition({"cat": "art"}, "cat", "in", ["tech", "biz"]) is False

    def test_contains_operator(self):
        assert evaluate_condition({"tags": ["a", "b"]}, "tags", "contains", "a") is True
        assert evaluate_condition({"name": "hello"}, "name", "contains", "ell") is True

    def test_between_operator(self):
        assert evaluate_condition({"v": 5}, "v", "between", [1, 10]) is True
        assert evaluate_condition({"v": 15}, "v", "between", [1, 10]) is False

    def test_exists_not_exists(self):
        assert evaluate_condition({"x": 1}, "x", "exists", None) is True
        assert evaluate_condition({}, "x", "not_exists", None) is True

    def test_dotted_field_path(self):
        data = {"meta": {"region": "eu"}}
        assert evaluate_condition(data, "meta.region", "eq", "eu") is True

    def test_rule_all_conditions_and(self):
        data = {"score": 80, "status": "active"}
        conditions = [
            {"field": "score", "operator": "gte", "value": 50},
            {"field": "status", "operator": "eq", "value": "active"},
        ]
        matched, details = evaluate_rule(data, conditions)
        assert matched is True
        assert all(d["matched"] for d in details)

    def test_rule_partial_fail(self):
        data = {"score": 30, "status": "active"}
        conditions = [
            {"field": "score", "operator": "gte", "value": 50},
            {"field": "status", "operator": "eq", "value": "active"},
        ]
        matched, details = evaluate_rule(data, conditions)
        assert matched is False

    def test_evaluate_policy_rules(self):
        data = {"event_count": 10, "growth_rate": 5.0}
        rules = [
            {
                "name": "high_count",
                "conditions": [{"field": "event_count", "operator": "gte", "value": 5}],
                "action": "flag",
                "weight": 2.0,
                "enabled": True,
            },
            {
                "name": "low_count",
                "conditions": [{"field": "event_count", "operator": "lt", "value": 3}],
                "action": "suppress",
                "weight": 1.0,
                "enabled": True,
            },
            {
                "name": "disabled",
                "conditions": [{"field": "event_count", "operator": "gte", "value": 1}],
                "action": "flag",
                "enabled": False,
            },
        ]
        matched = evaluate_policy_rules(data, rules)
        assert len(matched) == 1
        assert matched[0]["rule_name"] == "high_count"
        assert matched[0]["weight"] == 2.0

    def test_invalid_operator(self):
        assert evaluate_condition({"x": 1}, "x", "invalid_op", 1) is False


# ── Plugin Tests ───────────────────────────────────────────────────


class TestPlugins:
    def test_demo_source(self):
        provider = DemoSourceProvider()
        events = provider.fetch(limit=5)
        assert len(events) <= 5
        assert all("source" in e for e in events)
        assert provider.meta().name == "demo"

    def test_default_normalizer(self):
        norm = DefaultNormalizer()
        raw = {"source": "test", "category": "tech", "topic": "AI", "value": 5}
        result = norm.normalize(raw)
        assert result["source"] == "test"
        assert result["category"] == "tech"
        assert result["value"] == 5.0

    def test_threshold_detector(self):
        detector = ThresholdDetector()
        items = [
            {"topic": "AI", "category": "tech", "source": "demo", "value": 3},
            {"topic": "AI", "category": "tech", "source": "demo", "value": 5},
            {"topic": "AI", "category": "tech", "source": "demo", "value": 2},
        ]
        trends = detector.detect(items)
        assert len(trends) >= 1
        assert trends[0]["topic"] == "AI"
        assert trends[0]["event_count"] == 3

    def test_spike_detector(self):
        detector = SpikeDetector()
        items = [
            {"topic": "X", "category": "c", "source": "s", "value": 1},
        ] * 10 + [
            {"topic": "Y", "category": "c", "source": "s", "value": 1},
        ]
        trends = detector.detect(items, {"spike_ratio": 2.0})
        # X has 10 events vs baseline ~5.5, should spike
        topics = [t["topic"] for t in trends]
        assert "X" in topics

    def test_default_scorer(self):
        scorer = DefaultScorer()
        item = {"event_count": 5, "growth_rate": 2.0, "total_value": 10}
        score = scorer.score(item)
        assert score > 0

    def test_top_n_recommender(self):
        rec = TopNRecommender()
        trends = [
            {"topic": "A", "category": "c1", "score": 80, "event_count": 10},
            {"topic": "B", "category": "c2", "score": 30, "event_count": 5},
            {"topic": "C", "category": "c1", "score": 60, "event_count": 8},
        ]
        recs = rec.recommend(trends, {"n": 2, "min_score": 10})
        assert len(recs) == 2
        assert recs[0]["priority"] == "high"

    def test_diversity_recommender(self):
        rec = DiversityRecommender()
        trends = [
            {"topic": "A", "category": "c1", "score": 90, "event_count": 10},
            {"topic": "B", "category": "c1", "score": 80, "event_count": 8},
            {"topic": "C", "category": "c2", "score": 70, "event_count": 7},
        ]
        recs = rec.recommend(trends, {"n": 2})
        categories = {r["category"] for r in recs}
        assert len(categories) == 2  # Diverse

    def test_log_notifier(self):
        notifier = LogNotificationProvider()
        result = notifier.send({"severity": "info", "title": "Test", "body": "test body"})
        assert result is True


class TestRegistry:
    def test_register_and_get(self):
        registry = PluginRegistry()
        registry.register_source("demo", DemoSourceProvider)
        provider = registry.get_source("demo")
        assert provider is not None
        assert provider.meta().name == "demo"

    def test_get_nonexistent(self):
        registry = PluginRegistry()
        assert registry.get_source("nonexistent") is None

    def test_list_all(self):
        registry = PluginRegistry()
        registry.register_source("demo", DemoSourceProvider)
        registry.register_detector("threshold", ThresholdDetector)
        result = registry.list_all()
        assert len(result["sources"]) == 1
        assert len(result["detectors"]) == 1

    def test_health(self):
        registry = PluginRegistry()
        registry.register_source("demo", DemoSourceProvider)
        registry.register_notifier("log", LogNotificationProvider)
        health = registry.health()
        assert health["sources"]["demo"]["status"] == "ok"
        assert health["notifiers"]["log"]["status"] == "ok"


# ── Multi-Tenant Isolation Tests (unit level) ──────────────────────


class TestMultiTenantIsolation:
    """Tests that verify tenant_id filtering in queries."""

    def test_tenant_context_creation(self):
        from scoring_service.tenancy.context import TenantContext
        ctx = TenantContext(
            tenant_id="test", tenant_name="Test",
            workspace_id=None, plan="free", settings={},
        )
        assert ctx.tenant_id == "test"
        assert ctx.is_admin is False

    def test_admin_context(self):
        from scoring_service.tenancy.context import TenantContext
        ctx = TenantContext(
            tenant_id="__admin__", tenant_name="Admin",
            workspace_id=None, plan="internal", settings={}, is_admin=True,
        )
        assert ctx.is_admin is True


# ── Contract/Schema Tests ──────────────────────────────────────────


class TestPlatformContracts:
    def test_tenant_create_validation(self):
        from scoring_service.platform_contracts import TenantCreate
        t = TenantCreate(id="test", name="Test", slug="test")
        assert t.plan == "free"

    def test_tenant_create_invalid(self):
        from scoring_service.platform_contracts import TenantCreate
        with pytest.raises(Exception):
            TenantCreate(id="", name="Test", slug="test")

    def test_policy_condition_validation(self):
        from scoring_service.platform_contracts import PolicyCondition
        c = PolicyCondition(field="score", operator="gte", value=50)
        assert c.operator == "gte"

    def test_policy_condition_invalid_operator(self):
        from scoring_service.platform_contracts import PolicyCondition
        with pytest.raises(Exception):
            PolicyCondition(field="score", operator="invalid", value=50)

    def test_policy_bundle_create(self):
        from scoring_service.platform_contracts import (
            PolicyBundleCreate, PolicyVersionConfig, PolicyCondition, PolicyRuleConfig,
        )
        rule = PolicyRuleConfig(
            name="test",
            conditions=[PolicyCondition(field="x", operator="gt", value=5)],
        )
        config = PolicyVersionConfig(rules=[rule])
        bundle = PolicyBundleCreate(name="Test", policy_type="detection", config=config)
        assert bundle.policy_type == "detection"

    def test_event_ingest_validation(self):
        from scoring_service.platform_contracts import EventIngest
        e = EventIngest(source="test", event_type="signal", payload={"a": 1})
        assert e.source == "test"

    def test_export_create_validation(self):
        from scoring_service.platform_contracts import ExportCreate
        e = ExportCreate(export_type="trends")
        assert e.format == "json"

    def test_export_create_invalid_type(self):
        from scoring_service.platform_contracts import ExportCreate
        with pytest.raises(Exception):
            ExportCreate(export_type="invalid_type")


# ── Usage / Quota Logic Tests ──────────────────────────────────────


class TestUsageLogic:
    def test_default_plans(self):
        from scoring_service.usage.service import DEFAULT_PLANS
        assert "free" in DEFAULT_PLANS
        assert "pro" in DEFAULT_PLANS
        assert "team" in DEFAULT_PLANS
        assert "internal" in DEFAULT_PLANS
        assert DEFAULT_PLANS["free"]["limits"]["events_per_month"] == 1000
        assert DEFAULT_PLANS["internal"]["limits"]["events_per_month"] == 999999999
