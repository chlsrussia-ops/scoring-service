"""Tests for source providers."""
from __future__ import annotations

import pytest
from scoring_service.sources.reddit_source import RedditSourceProvider
from scoring_service.sources.file_source import FileSourceProvider
from scoring_service.sources.base import SourceEvent


@pytest.mark.asyncio
async def test_reddit_mock_mode():
    provider = RedditSourceProvider({"subreddits": ["technology"], "mock_mode": True})
    events, cursor = await provider.fetch()
    assert len(events) > 0
    assert all(isinstance(e, SourceEvent) for e in events)
    assert cursor is None


@pytest.mark.asyncio
async def test_reddit_mock_test_connection():
    provider = RedditSourceProvider({"subreddits": ["technology"], "mock_mode": True})
    result = await provider.test_connection()
    assert result.ok


@pytest.mark.asyncio
async def test_file_json_inline():
    data = '[{"title": "Test Event", "body": "Test body", "category": "test"}]'
    provider = FileSourceProvider({"content": data, "format": "json"})
    events, _ = await provider.fetch()
    assert len(events) == 1
    assert events[0].title == "Test Event"


@pytest.mark.asyncio
async def test_file_csv_inline():
    csv_data = "title,body,category\nEvent 1,Body 1,tech\nEvent 2,Body 2,biz"
    provider = FileSourceProvider({"content": csv_data, "format": "csv"})
    events, _ = await provider.fetch()
    assert len(events) == 2


def test_source_event_hash():
    ev = SourceEvent(external_id="test1", source_type="rss", source_name="test", title="Hello")
    assert ev.content_hash
    assert len(ev.content_hash) == 16


def test_reddit_validate_config():
    provider = RedditSourceProvider({"subreddits": []})
    errors = provider.validate_config()
    assert len(errors) > 0

    provider2 = RedditSourceProvider({"subreddits": ["test"]})
    assert len(provider2.validate_config()) == 0
