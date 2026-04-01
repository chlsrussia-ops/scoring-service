from __future__ import annotations

from scoring_service.contracts import ScoreBreakdown, ScoreRequest, ScoreResult


def fallback_result(request: ScoreRequest, reason: str) -> ScoreResult:
    breakdown = ScoreBreakdown(
        base_score=0.0,
        item_count=len(request.payload) if isinstance(request.payload, dict) else 0,
        numeric_sum=0.0,
        text_weight=0.0,
        bonuses={},
        numeric_fields_count=0,
        text_fields_count=0,
        collection_fields_count=0,
        nested_fields_count=0,
        bool_true_fields_count=0,
    )
    return ScoreResult(
        ok=False,
        final_score=0.0,
        capped=False,
        used_fallback=True,
        reason=reason,
        breakdown=breakdown,
        request_id=request.request_id,
        source=request.source,
        diagnostics=(f"fallback: {reason}",),
    )
