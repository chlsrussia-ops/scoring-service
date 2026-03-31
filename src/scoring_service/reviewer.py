from __future__ import annotations

from scoring_service.config import Settings
from scoring_service.contracts import ReviewDecision, ScoreResult


def review(result: ScoreResult, settings: Settings) -> ReviewDecision:
    if not result.ok:
        return ReviewDecision(approved=False, label="rejected", reason="result is not ok")

    if result.final_score >= settings.reviewer_excellent_threshold:
        return ReviewDecision(approved=True, label="excellent", reason="score is very strong")

    if result.final_score >= settings.reviewer_approved_threshold:
        return ReviewDecision(approved=True, label="approved", reason="score passed threshold")

    if result.final_score >= settings.reviewer_manual_review_threshold:
        return ReviewDecision(
            approved=False, label="manual_review", reason="needs manual inspection"
        )

    return ReviewDecision(
        approved=False, label="rejected", reason="score below acceptable threshold"
    )
