"""Tests for mock LLM provider."""
from __future__ import annotations

import pytest
from scoring_service.llm.mock_provider import MockLlmProvider
from scoring_service.llm.base import LlmRequest


@pytest.mark.asyncio
async def test_mock_trend_summary():
    provider = MockLlmProvider()
    assert provider.is_available()
    request = LlmRequest(
        prompt="trend_summary analysis\nTopic: AI Content Tools\nCategory: technology\nScore: 85",
        system="Test system prompt",
    )
    response = await provider.generate(request)
    assert response.text
    assert response.provider == "mock"
    assert response.tokens_used > 0
    assert "AI Content Tools" in response.text or "Trend Summary" in response.text


@pytest.mark.asyncio
async def test_mock_recommendation():
    provider = MockLlmProvider()
    request = LlmRequest(
        prompt="recommendation enhance\nTitle: Publish content on AI tools",
    )
    response = await provider.generate(request)
    assert response.text
    assert "Recommendation" in response.text or "Action" in response.text


@pytest.mark.asyncio
async def test_mock_digest():
    provider = MockLlmProvider()
    request = LlmRequest(prompt="Generate executive digest briefing for content team")
    response = await provider.generate(request)
    assert response.text
    assert "Briefing" in response.text or "Key" in response.text


@pytest.mark.asyncio
async def test_mock_alert():
    provider = MockLlmProvider()
    request = LlmRequest(prompt="alert explain\nTitle: Trend spike detected")
    response = await provider.generate(request)
    assert response.text


@pytest.mark.asyncio
async def test_mock_determinism():
    provider = MockLlmProvider()
    req = LlmRequest(prompt="trend_summary analysis\nTopic: Test Topic")
    r1 = await provider.generate(req)
    r2 = await provider.generate(req)
    assert r1.text == r2.text
