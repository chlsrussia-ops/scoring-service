"""Structured logging and diagnostics with correlation ID support."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Iterable

LOGGER_NAME = "scoring_service"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from scoring_service.correlation import get_correlation_id

        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id() or None,
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level_name: str = "INFO", *, json_logs: bool = True) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    level = getattr(logging, level_name.upper(), logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if json_logs:
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
            )
        logger.addHandler(handler)

    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def collect_diagnostics(limit: int, *messages: str) -> tuple[str, ...]:
    items = [m for m in messages if m]
    return tuple(items[:limit])


def log_lines(lines: Iterable[str]) -> None:
    logger = get_logger()
    for line in lines:
        logger.info(line)
