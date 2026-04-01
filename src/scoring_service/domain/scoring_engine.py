from __future__ import annotations

from typing import Any

from scoring_service.config import Settings
from scoring_service.contracts import ScoreBreakdown, ScoreRequest


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def compute_breakdown(request: ScoreRequest, settings: Settings) -> ScoreBreakdown:
    payload = request.payload

    item_count = len(payload)
    numeric_sum = 0.0
    text_weight = 0.0
    bonuses: dict[str, float] = {}

    numeric_fields_count = 0
    text_fields_count = 0
    collection_fields_count = 0
    nested_fields_count = 0
    bool_true_fields_count = 0

    for key, value in payload.items():
        if _is_number(value):
            numeric_fields_count += 1
            numeric_sum += float(value)
            continue

        if isinstance(value, str):
            text_fields_count += 1
            text_weight += min(len(value) * 0.25, settings.max_text_weight_per_field)
            continue

        if isinstance(value, (list, tuple, set)):
            collection_fields_count += 1
            bonuses[f"{key}_collection_bonus"] = min(
                len(value) * settings.collection_weight,
                settings.max_collection_bonus,
            )
            continue

        if isinstance(value, dict):
            nested_fields_count += 1
            bonuses[f"{key}_nested_bonus"] = min(
                len(value) * settings.nested_weight,
                settings.max_nested_bonus,
            )
            continue

        if value is True:
            bool_true_fields_count += 1
            bonuses[f"{key}_flag_bonus"] = settings.true_flag_bonus
            continue

    base_score = (
        item_count * settings.item_weight
        + numeric_sum * settings.numeric_multiplier
        + text_weight
        + sum(bonuses.values())
    )

    return ScoreBreakdown(
        base_score=round(base_score, 4),
        item_count=item_count,
        numeric_sum=round(numeric_sum, 4),
        text_weight=round(text_weight, 4),
        bonuses=bonuses,
        numeric_fields_count=numeric_fields_count,
        text_fields_count=text_fields_count,
        collection_fields_count=collection_fields_count,
        nested_fields_count=nested_fields_count,
        bool_true_fields_count=bool_true_fields_count,
    )
