from scoring_service.config import Settings
from scoring_service.contracts import ReviewDecision, ScoreBreakdown, ScoreResult
from scoring_service.reviewer import review


def _result(score: float, ok: bool = True) -> ScoreResult:
    return ScoreResult(
        ok=ok,
        final_score=score,
        capped=False,
        used_fallback=not ok,
        reason=None if ok else "failed",
        breakdown=ScoreBreakdown(
            base_score=score,
            item_count=1,
            numeric_sum=0.0,
            text_weight=0.0,
            bonuses={},
        ),
        request_id="r1",
        source="test",
        diagnostics=(),
    )


def test_reviewer_approved() -> None:
    decision: ReviewDecision = review(_result(55.0), Settings())
    assert decision.approved is True
    assert decision.label == "approved"


def test_reviewer_manual_review() -> None:
    decision = review(_result(25.0), Settings())
    assert decision.approved is False
    assert decision.label == "manual_review"


def test_reviewer_rejected_when_not_ok() -> None:
    decision = review(_result(0.0, ok=False), Settings())
    assert decision.approved is False
    assert decision.label == "rejected"
