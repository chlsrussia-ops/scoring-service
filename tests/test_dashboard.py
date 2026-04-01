"""Tests for dashboard, sources, LLM, and demo endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from scoring_service.api.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health():
    client = _client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["product"] == "TrendIntel"


def test_ready():
    client = _client()
    r = client.get("/ready")
    assert r.status_code == 200


def test_dashboard_overview():
    client = _client()
    r = client.get("/v1/dashboard/overview?tenant_id=demo")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data
    assert "trends" in data


def test_dashboard_trends():
    client = _client()
    r = client.get("/v1/dashboard/trends?tenant_id=demo")
    assert r.status_code == 200
    assert "items" in r.json()


def test_dashboard_recommendations():
    client = _client()
    r = client.get("/v1/dashboard/recommendations?tenant_id=demo")
    assert r.status_code == 200
    assert "items" in r.json()


def test_dashboard_alerts():
    client = _client()
    r = client.get("/v1/dashboard/alerts?tenant_id=demo")
    assert r.status_code == 200
    assert "items" in r.json()


def test_sources_list():
    client = _client()
    r = client.get("/v1/sources?tenant_id=demo")
    assert r.status_code == 200
    assert "items" in r.json()


def test_sources_create():
    client = _client()
    r = client.post("/v1/sources?tenant_id=demo", json={
        "name": "Test RSS",
        "source_type": "rss",
        "config_json": {"feeds": ["https://example.com/feed"]},
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Test RSS"


def test_llm_generations():
    client = _client()
    r = client.get("/v1/llm/generations?tenant_id=demo")
    assert r.status_code == 200


def test_llm_digests():
    client = _client()
    r = client.get("/v1/llm/digests?tenant_id=demo")
    assert r.status_code == 200


def test_demo_status():
    client = _client()
    r = client.get("/v1/demo/status")
    assert r.status_code == 200
    assert "tenant_id" in r.json()


def test_demo_seed():
    client = _client()
    r = client.post("/v1/demo/seed")
    assert r.status_code == 200
    data = r.json()
    assert data.get("events", 0) > 0 or "events" in data
