"""Built-in plugin implementations."""
from __future__ import annotations

import hashlib
import math
import random
from typing import Any

from scoring_service.plugins.base import (
    BaseDetector,
    BaseNormalizer,
    BaseNotificationProvider,
    BaseRecommender,
    BaseScorer,
    BaseSourceProvider,
    ProviderMeta,
)


# ── Source Providers ────────────────────────────────────────

class DemoSourceProvider(BaseSourceProvider):
    """Generates demo events for testing."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="demo",
            description="Demo event source for testing",
            capabilities=["fetch"],
        )

    def fetch(self, *, since: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        categories = ["tech", "business", "health", "entertainment", "science"]
        topics = [
            "AI adoption", "remote work", "crypto regulation", "green energy",
            "fitness tracking", "streaming wars", "quantum computing",
            "space exploration", "gene therapy", "autonomous vehicles",
        ]
        events = []
        for i in range(min(limit, 20)):
            events.append({
                "source": "demo",
                "event_type": "trend_signal",
                "external_id": f"demo-{i}-{random.randint(1000,9999)}",
                "category": random.choice(categories),
                "topic": random.choice(topics),
                "value": round(random.uniform(0.1, 10.0), 2),
                "metadata": {"generated": True, "batch": i},
            })
        return events


class WebhookSourceProvider(BaseSourceProvider):
    """Receives events via webhook (events pushed, not pulled)."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="webhook",
            description="Webhook-based event source",
            capabilities=["push"],
        )

    def fetch(self, *, since: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return []  # Webhook events come via API push, not fetch


class RSSSourceProvider(BaseSourceProvider):
    """Simulates RSS feed source."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="rss",
            description="RSS/Atom feed source provider",
            capabilities=["fetch", "incremental"],
        )

    def fetch(self, *, since: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        # Placeholder — real implementation would parse feeds
        return [
            {
                "source": "rss",
                "event_type": "article",
                "external_id": f"rss-{i}",
                "category": "news",
                "topic": f"RSS article {i}",
                "value": 1.0,
                "metadata": {"feed_url": "https://example.com/feed"},
            }
            for i in range(min(limit, 5))
        ]


# ── Normalizer ──────────────────────────────────────────────

class DefaultNormalizer(BaseNormalizer):
    def meta(self) -> ProviderMeta:
        return ProviderMeta(name="default", description="Default event normalizer")

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": raw.get("source", "unknown"),
            "category": raw.get("category", "uncategorized"),
            "topic": raw.get("topic", "unknown"),
            "value": float(raw.get("value", 0)),
            "event_type": raw.get("event_type", "generic"),
            "external_id": raw.get("external_id"),
            "metadata": raw.get("metadata", {}),
        }


# ── Detectors ───────────────────────────────────────────────

class ThresholdDetector(BaseDetector):
    """Detects trends when signal count or value exceeds threshold."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="threshold",
            description="Threshold-based trend detection",
            capabilities=["batch"],
        )

    def detect(self, items: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = context or {}
        min_count = ctx.get("min_count", 2)
        min_value = ctx.get("min_value", 1.0)

        # Group by topic
        topic_groups: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            topic = item.get("topic", "unknown")
            topic_groups.setdefault(topic, []).append(item)

        trends = []
        for topic, group in topic_groups.items():
            if len(group) >= min_count:
                total_value = sum(float(i.get("value", 0)) for i in group)
                if total_value >= min_value:
                    trends.append({
                        "topic": topic,
                        "category": group[0].get("category", "uncategorized"),
                        "source": group[0].get("source", "unknown"),
                        "event_count": len(group),
                        "total_value": total_value,
                        "direction": "rising",
                        "growth_rate": total_value / max(len(group), 1),
                    })
        return trends


class SpikeDetector(BaseDetector):
    """Detects spikes — sudden increases in signal frequency."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="spike",
            description="Spike-based trend detection",
            capabilities=["batch", "time_aware"],
        )

    def detect(self, items: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = context or {}
        spike_ratio = ctx.get("spike_ratio", 2.0)

        topic_groups: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            topic = item.get("topic", "unknown")
            topic_groups.setdefault(topic, []).append(item)

        baseline = max(1, len(items) / max(len(topic_groups), 1))
        trends = []
        for topic, group in topic_groups.items():
            if len(group) >= baseline * spike_ratio:
                total_value = sum(float(i.get("value", 0)) for i in group)
                trends.append({
                    "topic": topic,
                    "category": group[0].get("category", "uncategorized"),
                    "source": group[0].get("source", "unknown"),
                    "event_count": len(group),
                    "total_value": total_value,
                    "direction": "spike",
                    "growth_rate": len(group) / max(baseline, 0.1),
                })
        return trends


# ── Scorers ─────────────────────────────────────────────────

class DefaultScorer(BaseScorer):
    def meta(self) -> ProviderMeta:
        return ProviderMeta(name="default", description="Default trend scorer")

    def score(self, item: dict[str, Any], weights: dict[str, float] | None = None) -> float:
        w = weights or {}
        event_w = w.get("event_count", 2.0)
        growth_w = w.get("growth_rate", 5.0)
        value_w = w.get("total_value", 1.0)

        score = (
            item.get("event_count", 0) * event_w
            + item.get("growth_rate", 0) * growth_w
            + item.get("total_value", 0) * value_w
        )
        return min(round(score, 2), 100.0)


# ── Recommenders ────────────────────────────────────────────

class TopNRecommender(BaseRecommender):
    """Recommends top N trends by score."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="top_n",
            description="Recommends top-scored trends",
            capabilities=["ranked"],
        )

    def recommend(self, trends: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = context or {}
        n = ctx.get("n", 5)
        min_score = ctx.get("min_score", 10.0)

        sorted_trends = sorted(trends, key=lambda t: t.get("score", 0), reverse=True)
        recs = []
        for t in sorted_trends[:n]:
            if t.get("score", 0) >= min_score:
                score = t.get("score", 0)
                recs.append({
                    "trend_topic": t.get("topic", ""),
                    "category": t.get("category", ""),
                    "title": f"Trending: {t.get('topic', 'unknown')}",
                    "body": f"Topic '{t.get('topic')}' scored {score:.1f} with {t.get('event_count', 0)} events",
                    "priority": "high" if score >= 50 else "medium",
                    "confidence": min(score / 100.0, 1.0),
                })
        return recs


class DiversityRecommender(BaseRecommender):
    """Recommends trends with category diversity."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="diversity",
            description="Category-diverse recommendations",
            capabilities=["ranked", "diverse"],
        )

    def recommend(self, trends: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = context or {}
        n = ctx.get("n", 5)
        sorted_trends = sorted(trends, key=lambda t: t.get("score", 0), reverse=True)

        seen_categories: set[str] = set()
        recs = []
        for t in sorted_trends:
            cat = t.get("category", "")
            if cat in seen_categories and len(recs) < n:
                continue
            seen_categories.add(cat)
            score = t.get("score", 0)
            recs.append({
                "trend_topic": t.get("topic", ""),
                "category": cat,
                "title": f"Trending: {t.get('topic', 'unknown')}",
                "body": f"Diverse pick from '{cat}': score {score:.1f}",
                "priority": "high" if score >= 50 else "medium",
                "confidence": min(score / 100.0, 1.0),
            })
            if len(recs) >= n:
                break
        return recs


# ── Notification Providers ──────────────────────────────────

class LogNotificationProvider(BaseNotificationProvider):
    """Logs alerts to stdout (default fallback)."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="log",
            description="Log-based notification (stdout)",
            capabilities=["sync"],
        )

    def send(self, alert: dict[str, Any]) -> bool:
        import logging
        logging.getLogger("scoring_service.alerts").info(
            "ALERT [%s] %s: %s",
            alert.get("severity", "info"),
            alert.get("title", "untitled"),
            alert.get("body", ""),
        )
        return True


class WebhookNotificationProvider(BaseNotificationProvider):
    """Sends alerts via HTTP webhook."""

    def meta(self) -> ProviderMeta:
        return ProviderMeta(
            name="webhook",
            description="HTTP webhook notification provider",
            capabilities=["async", "http"],
        )

    def send(self, alert: dict[str, Any]) -> bool:
        # Placeholder — real impl would POST to configured URL
        import logging
        logging.getLogger("scoring_service.alerts").info(
            "WEBHOOK alert: %s", alert.get("title", "")
        )
        return True


def register_builtins(registry: Any) -> None:
    """Register all built-in providers."""
    registry.register_source("demo", DemoSourceProvider)
    registry.register_source("webhook", WebhookSourceProvider)
    registry.register_source("rss", RSSSourceProvider)
    registry.register_normalizer("default", DefaultNormalizer)
    registry.register_detector("threshold", ThresholdDetector)
    registry.register_detector("spike", SpikeDetector)
    registry.register_scorer("default", DefaultScorer)
    registry.register_recommender("top_n", TopNRecommender)
    registry.register_recommender("diversity", DiversityRecommender)
    registry.register_notifier("log", LogNotificationProvider)
    registry.register_notifier("webhook", WebhookNotificationProvider)
