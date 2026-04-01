"""Plugin registry — register, discover, instantiate providers."""
from __future__ import annotations

import logging
from typing import Any, Type

from scoring_service.plugins.base import (
    BaseDetector,
    BaseNormalizer,
    BaseNotificationProvider,
    BaseRecommender,
    BaseScorer,
    BaseSourceProvider,
    ProviderMeta,
)

logger = logging.getLogger("scoring_service.plugins")

ProviderType = (
    Type[BaseSourceProvider]
    | Type[BaseNormalizer]
    | Type[BaseDetector]
    | Type[BaseScorer]
    | Type[BaseRecommender]
    | Type[BaseNotificationProvider]
)


class PluginRegistry:
    """Central registry for all plugin providers."""

    def __init__(self) -> None:
        self._sources: dict[str, Type[BaseSourceProvider]] = {}
        self._normalizers: dict[str, Type[BaseNormalizer]] = {}
        self._detectors: dict[str, Type[BaseDetector]] = {}
        self._scorers: dict[str, Type[BaseScorer]] = {}
        self._recommenders: dict[str, Type[BaseRecommender]] = {}
        self._notifiers: dict[str, Type[BaseNotificationProvider]] = {}

    # ── Registration ────────────────────────────────────────

    def register_source(self, name: str, cls: Type[BaseSourceProvider]) -> None:
        self._sources[name] = cls
        logger.info("Registered source provider: %s", name)

    def register_normalizer(self, name: str, cls: Type[BaseNormalizer]) -> None:
        self._normalizers[name] = cls

    def register_detector(self, name: str, cls: Type[BaseDetector]) -> None:
        self._detectors[name] = cls
        logger.info("Registered detector: %s", name)

    def register_scorer(self, name: str, cls: Type[BaseScorer]) -> None:
        self._scorers[name] = cls

    def register_recommender(self, name: str, cls: Type[BaseRecommender]) -> None:
        self._recommenders[name] = cls
        logger.info("Registered recommender: %s", name)

    def register_notifier(self, name: str, cls: Type[BaseNotificationProvider]) -> None:
        self._notifiers[name] = cls
        logger.info("Registered notifier: %s", name)

    # ── Lookup ──────────────────────────────────────────────

    def get_source(self, name: str) -> BaseSourceProvider | None:
        cls = self._sources.get(name)
        return cls() if cls else None

    def get_normalizer(self, name: str) -> BaseNormalizer | None:
        cls = self._normalizers.get(name)
        return cls() if cls else None

    def get_detector(self, name: str) -> BaseDetector | None:
        cls = self._detectors.get(name)
        return cls() if cls else None

    def get_scorer(self, name: str) -> BaseScorer | None:
        cls = self._scorers.get(name)
        return cls() if cls else None

    def get_recommender(self, name: str) -> BaseRecommender | None:
        cls = self._recommenders.get(name)
        return cls() if cls else None

    def get_notifier(self, name: str) -> BaseNotificationProvider | None:
        cls = self._notifiers.get(name)
        return cls() if cls else None

    # ── Discovery ───────────────────────────────────────────

    def list_all(self) -> dict[str, list[dict[str, Any]]]:
        def _metas(registry: dict[str, Any]) -> list[dict[str, Any]]:
            result = []
            for name, cls in registry.items():
                try:
                    inst = cls()
                    m = inst.meta()
                    result.append({
                        "name": name,
                        "version": m.version,
                        "description": m.description,
                        "capabilities": m.capabilities,
                    })
                except Exception as e:
                    result.append({"name": name, "error": str(e)})
            return result

        return {
            "sources": _metas(self._sources),
            "normalizers": _metas(self._normalizers),
            "detectors": _metas(self._detectors),
            "scorers": _metas(self._scorers),
            "recommenders": _metas(self._recommenders),
            "notifiers": _metas(self._notifiers),
        }

    def health(self) -> dict[str, Any]:
        """Health check all registered providers."""
        result: dict[str, Any] = {}
        for category, registry in [
            ("sources", self._sources),
            ("notifiers", self._notifiers),
        ]:
            checks = {}
            for name, cls in registry.items():
                try:
                    inst = cls()
                    checks[name] = inst.health()
                except Exception as e:
                    checks[name] = {"status": "error", "error": str(e)}
            result[category] = checks
        return result


# Global singleton
plugin_registry = PluginRegistry()
