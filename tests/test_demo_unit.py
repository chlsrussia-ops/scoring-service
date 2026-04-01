"""Tests for demo seed data generation."""
from __future__ import annotations

from scoring_service.demo.seed_data import (
    generate_alerts, generate_demo_sources, generate_events,
    generate_recommendations, generate_trends,
)


def test_generate_events():
    events = generate_events(100)
    assert len(events) == 100
    assert all("external_id" in e for e in events)
    assert all("title" in e for e in events)
    categories = {e["category"] for e in events}
    assert len(categories) > 3


def test_generate_events_default_count():
    events = generate_events()
    assert len(events) == 1200


def test_generate_trends():
    trends = generate_trends()
    assert len(trends) > 10
    assert all("topic" in t for t in trends)
    assert all("score" in t for t in trends)
    high = [t for t in trends if t["score"] > 60]
    assert len(high) > 5


def test_generate_recommendations():
    trends = generate_trends()
    recs = generate_recommendations(trends)
    assert len(recs) > 5
    assert all("title" in r for r in recs)
    priorities = {r["priority"] for r in recs}
    assert "high" in priorities


def test_generate_alerts():
    trends = generate_trends()
    alerts = generate_alerts(trends)
    assert len(alerts) > 0
    assert all("severity" in a for a in alerts)


def test_generate_demo_sources():
    sources = generate_demo_sources()
    assert len(sources) >= 4
    types = {s["source_type"] for s in sources}
    assert "rss" in types
    assert "reddit" in types
