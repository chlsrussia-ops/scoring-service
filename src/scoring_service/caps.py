from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapResult:
    value: float
    capped: bool
    cap_limit: float
    min_limit: float


def apply_caps(value: float, *, min_value: float, max_value: float) -> CapResult:
    normalized = max(min_value, min(value, max_value))
    return CapResult(
        value=round(normalized, 4),
        capped=(normalized != value),
        cap_limit=max_value,
        min_limit=min_value,
    )
