"""Base provider interfaces for the plugin system."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderMeta:
    name: str
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = field(default_factory=list)


class BaseSourceProvider(ABC):
    """Fetches raw events from an external source."""

    @abstractmethod
    def meta(self) -> ProviderMeta: ...

    @abstractmethod
    def fetch(self, *, since: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "provider": self.meta().name}


class BaseNormalizer(ABC):
    """Normalizes raw event payload into a standard schema."""

    @abstractmethod
    def meta(self) -> ProviderMeta: ...

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]: ...


class BaseDetector(ABC):
    """Detects signals/trends from normalized data."""

    @abstractmethod
    def meta(self) -> ProviderMeta: ...

    @abstractmethod
    def detect(self, items: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


class BaseScorer(ABC):
    """Assigns scores to detected trends/signals."""

    @abstractmethod
    def meta(self) -> ProviderMeta: ...

    @abstractmethod
    def score(self, item: dict[str, Any], weights: dict[str, float] | None = None) -> float: ...


class BaseRecommender(ABC):
    """Generates recommendations from scored trends."""

    @abstractmethod
    def meta(self) -> ProviderMeta: ...

    @abstractmethod
    def recommend(self, trends: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


class BaseNotificationProvider(ABC):
    """Sends notifications/alerts via a channel."""

    @abstractmethod
    def meta(self) -> ProviderMeta: ...

    @abstractmethod
    def send(self, alert: dict[str, Any]) -> bool: ...

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "provider": self.meta().name}
