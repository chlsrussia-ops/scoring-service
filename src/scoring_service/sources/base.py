"""Base source provider interface and unified event schema."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class SourceEvent(BaseModel):
    """Unified event schema for all source providers."""
    external_id: str
    source_type: str
    source_name: str
    title: str
    body: str = ""
    url: str = ""
    author: str = ""
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        content = f"{self.source_type}:{self.external_id}:{self.title}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class SourceHealthInfo(BaseModel):
    status: str = "unknown"
    last_sync_at: datetime | None = None
    items_fetched: int = 0
    items_normalized: int = 0
    failure_count: int = 0
    last_error: str | None = None


class SourceTestResult(BaseModel):
    ok: bool
    message: str
    items_preview: int = 0


class BaseSourceProvider(ABC):
    """Abstract base class for data source providers."""
    source_type: str = "unknown"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    async def fetch(self, cursor: str | None = None) -> tuple[list[SourceEvent], str | None]:
        """Fetch events. Returns (events, next_cursor)."""
        ...

    @abstractmethod
    async def test_connection(self) -> SourceTestResult:
        """Test if the source is reachable and configured properly."""
        ...

    def validate_config(self) -> list[str]:
        """Return list of config validation errors, empty if valid."""
        return []
