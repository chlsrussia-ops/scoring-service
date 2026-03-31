from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "scoring-service"
    log_level: str = "INFO"
    min_score: float = 0.0
    max_score: float = 100.0
    max_text_weight_per_field: float = 10.0
    max_collection_bonus: float = 8.0
    max_nested_bonus: float = 12.0
    numeric_multiplier: float = 0.10
    item_weight: float = 2.0
    collection_weight: float = 0.75
    nested_weight: float = 1.5
    true_flag_bonus: float = 2.0
    emit_metrics: bool = True
    emit_analytics: bool = True
    pretty_json_indent: int = 2
    fallback_on_error: bool = True
    reviewer_excellent_threshold: float = 80.0
    reviewer_approved_threshold: float = 50.0
    reviewer_manual_review_threshold: float = 20.0
    max_diagnostics: int = 20

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("SCORING_APP_NAME", "scoring-service"),
            log_level=os.getenv("SCORING_LOG_LEVEL", "INFO").upper(),
            min_score=_get_float("SCORING_MIN_SCORE", 0.0),
            max_score=_get_float("SCORING_MAX_SCORE", 100.0),
            max_text_weight_per_field=_get_float("SCORING_MAX_TEXT_WEIGHT_PER_FIELD", 10.0),
            max_collection_bonus=_get_float("SCORING_MAX_COLLECTION_BONUS", 8.0),
            max_nested_bonus=_get_float("SCORING_MAX_NESTED_BONUS", 12.0),
            numeric_multiplier=_get_float("SCORING_NUMERIC_MULTIPLIER", 0.10),
            item_weight=_get_float("SCORING_ITEM_WEIGHT", 2.0),
            collection_weight=_get_float("SCORING_COLLECTION_WEIGHT", 0.75),
            nested_weight=_get_float("SCORING_NESTED_WEIGHT", 1.5),
            true_flag_bonus=_get_float("SCORING_TRUE_FLAG_BONUS", 2.0),
            emit_metrics=_get_bool("SCORING_EMIT_METRICS", True),
            emit_analytics=_get_bool("SCORING_EMIT_ANALYTICS", True),
            pretty_json_indent=_get_int("SCORING_PRETTY_JSON_INDENT", 2),
            fallback_on_error=_get_bool("SCORING_FALLBACK_ON_ERROR", True),
            reviewer_excellent_threshold=_get_float("SCORING_REVIEWER_EXCELLENT_THRESHOLD", 80.0),
            reviewer_approved_threshold=_get_float("SCORING_REVIEWER_APPROVED_THRESHOLD", 50.0),
            reviewer_manual_review_threshold=_get_float("SCORING_REVIEWER_MANUAL_REVIEW_THRESHOLD", 20.0),
            max_diagnostics=_get_int("SCORING_MAX_DIAGNOSTICS", 20),
        )
