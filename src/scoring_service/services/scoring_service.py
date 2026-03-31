from __future__ import annotations
from scoring_service.config import Settings
from scoring_service.contracts import ScoreRequest, ScoreResult, ReviewDecision
from scoring_service.scoring_engine import compute_breakdown
from scoring_service.caps import apply_caps
from scoring_service.fallback import fallback_result
from scoring_service.reviewer import review
from scoring_service.diagnostics import collect_diagnostics

class ScoringService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def execute(self, request: ScoreRequest) -> tuple[ScoreResult, ReviewDecision]:
        try:
            breakdown = compute_breakdown(request, self.settings)
            cap = apply_caps(breakdown.base_score, min_value=self.settings.min_score, max_value=self.settings.max_score)
            diag = collect_diagnostics(self.settings.max_diagnostics,
                f"items={breakdown.item_count}", f"numeric={breakdown.numeric_sum:.2f}",
                f"text_weight={breakdown.text_weight:.2f}", f"capped={cap.capped}")
            result = ScoreResult(
                ok=True, final_score=cap.value, capped=cap.capped, used_fallback=False,
                reason=None, breakdown=breakdown, request_id=request.request_id,
                source=request.source, diagnostics=diag)
        except Exception as e:
            if self.settings.fallback_on_error:
                result = fallback_result(request, str(e))
            else:
                raise
        rev = review(result, self.settings)
        return result, rev
