from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from scoring_service.analytics import track
from scoring_service.caps import apply_caps
from scoring_service.config import Settings
from scoring_service.contracts import ReviewDecision, ScoreRequest, ScoreResponse, ScoreResult
from scoring_service.diagnostics import collect_diagnostics, get_logger
from scoring_service.fallback import fallback_result
from scoring_service.observability import emit_event, emit_metric
from scoring_service.reviewer import review
from scoring_service.scoring_engine import compute_breakdown


class Executor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, request: ScoreRequest) -> tuple[ScoreResult, ReviewDecision]:
        logger = get_logger()

        try:
            logger.info(
                "validated request_id=%s source=%s payload_items=%s",
                request.request_id,
                request.source,
                len(request.payload),
            )

            breakdown = compute_breakdown(request, self.settings)
            cap_result = apply_caps(
                breakdown.base_score,
                min_value=self.settings.min_score,
                max_value=self.settings.max_score,
            )

            diagnostics = collect_diagnostics(
                self.settings.max_diagnostics,
                f"items={breakdown.item_count}",
                f"numeric_sum={breakdown.numeric_sum}",
                f"text_weight={breakdown.text_weight}",
                f"numeric_fields={breakdown.numeric_fields_count}",
                f"text_fields={breakdown.text_fields_count}",
                f"collection_fields={breakdown.collection_fields_count}",
                f"nested_fields={breakdown.nested_fields_count}",
                f"bool_true_fields={breakdown.bool_true_fields_count}",
                f"capped={cap_result.capped}",
            )

            result = ScoreResult(
                ok=True,
                final_score=cap_result.value,
                capped=cap_result.capped,
                used_fallback=False,
                reason=None,
                breakdown=breakdown,
                request_id=request.request_id,
                source=request.source,
                diagnostics=diagnostics,
            )

            decision = review(result, self.settings)

            if self.settings.emit_analytics:
                track(
                    "score_executed",
                    request_id=request.request_id,
                    source=request.source,
                    capped=result.capped,
                    review_label=decision.label,
                )

            if self.settings.emit_metrics:
                emit_metric("score.final", result.final_score, request_id=request.request_id)
                emit_metric("score.items", float(breakdown.item_count), request_id=request.request_id)
                emit_event("score.completed", request_id=request.request_id, ok=result.ok)

            return result, decision

        except (ValueError, TypeError, AttributeError, PydanticValidationError) as exc:
            logger.exception(
                "execution failed request_id=%s",
                getattr(request, "request_id", "unknown"),
            )
            if not self.settings.fallback_on_error:
                raise

            result = fallback_result(request, reason=str(exc))
            decision = review(result, self.settings)

            if self.settings.emit_analytics:
                track("score_fallback", request_id=result.request_id, source=result.source)

            if self.settings.emit_metrics:
                emit_event("score.failed", request_id=result.request_id, reason=result.reason or "unknown")

            return result, decision


def execute(request: ScoreRequest, settings: Settings) -> tuple[ScoreResult, ReviewDecision]:
    return Executor(settings).execute(request)


def execute_response(request: ScoreRequest, settings: Settings) -> ScoreResponse:
    result, decision = execute(request, settings)
    return ScoreResponse(result=result, review=decision)
