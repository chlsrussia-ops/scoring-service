from __future__ import annotations

from dataclasses import dataclass

from scoring_service.config import Settings
from scoring_service.contracts import ScoreResult


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    approved: bool
    label: str
    reason: str


def review(result: ScoreResult, settings: Settings) -> ReviewDecision:
    if not result.ok:
        return ReviewDecision(False, "rejected", "result is not ok")

    if result.final_score >= settings.reviewer_excellent_threshold:
        return ReviewDecision(True, "excellent", "score is very strong")

    if result.final_score >= settings.reviewer_approved_threshold:
        return ReviewDecision(True, "approved", "score passed threshold")

    if result.final_score >= settings.reviewer_manual_review_threshold:
        return ReviewDecision(False, "manual_review", "needs manual inspection")

    return ReviewDecision(False, "rejected", "score below acceptable threshold")
