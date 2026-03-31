from __future__ import annotations

import logging
import sys
from typing import Iterable

LOGGER_NAME = "scoring_service"


def configure_logging(level_name: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    level = getattr(logging, level_name.upper(), logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
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
