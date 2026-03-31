from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AnalyticsCollector:
    counters: Counter[str] = field(default_factory=Counter)

    def track(self, event: str, **dimensions: Any) -> None:
        self.counters[event] += 1
        dim_repr = " ".join(f"{k}={v}" for k, v in sorted(dimensions.items()))
        if dim_repr:
            print(f"[ANALYTICS] event={event} {dim_repr}")
        else:
            print(f"[ANALYTICS] event={event}")

    def snapshot(self) -> dict[str, int]:
        return dict(self.counters)


collector = AnalyticsCollector()


def track(event: str, **dimensions: Any) -> None:
    collector.track(event, **dimensions)
