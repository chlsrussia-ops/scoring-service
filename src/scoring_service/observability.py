from __future__ import annotations

from typing import Any

from scoring_service.diagnostics import get_logger


def emit_metric(name: str, value: float, **tags: Any) -> None:
    get_logger().debug("metric %s=%s %s", name, value, tags)


def emit_event(name: str, **payload: Any) -> None:
    get_logger().debug("event %s %s", name, payload)
