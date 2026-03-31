from __future__ import annotations

from typing import Any


def emit_metric(name: str, value: float, **tags: Any) -> None:
    tag_str = " ".join(f"{k}={v}" for k, v in sorted(tags.items()))
    if tag_str:
        print(f"[METRIC] {name}={value} {tag_str}")
    else:
        print(f"[METRIC] {name}={value}")


def emit_event(name: str, **payload: Any) -> None:
    payload_str = " ".join(f"{k}={v}" for k, v in sorted(payload.items()))
    if payload_str:
        print(f"[EVENT] {name} {payload_str}")
    else:
        print(f"[EVENT] {name}")
