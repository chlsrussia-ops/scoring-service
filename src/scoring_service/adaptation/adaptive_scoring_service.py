"""Adaptive Scoring Layer — adjusts scores without breaking deterministic base."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import AdaptationRepository, SourceLearningRepository
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


class AdaptiveScoringService:
    """Applies adaptive adjustments on top of base deterministic scores."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.adapt_repo = AdaptationRepository(db)
        self.source_repo = SourceLearningRepository(db)

    def adjust_score(
        self, tenant_id: str, entity_type: str, entity_id: int,
        base_score: float, source: str | None = None,
        category: str | None = None, topic: str | None = None,
    ) -> dict[str, Any]:
        """Apply adaptive adjustments. Returns adjusted score + explanation."""
        if not self.settings.adaptation_enabled:
            return {"base_score": base_score, "adjusted_score": base_score, "adjustments": {}, "explanation": "adaptation disabled"}

        profile = self.adapt_repo.get_active_profile(tenant_id)
        if not profile:
            return {"base_score": base_score, "adjusted_score": base_score, "adjustments": {}, "explanation": "no active profile"}

        adjustments: dict[str, float] = {}
        multiplier = 1.0

        # Source trust multiplier
        if source:
            src_trust = profile.source_trust_json.get(source)
            if src_trust is not None:
                src_mult = max(self.settings.adaptive_source_trust_min,
                               min(float(src_trust), self.settings.adaptive_source_trust_max))
                if src_mult != 1.0:
                    adjustments["source_trust"] = round(src_mult - 1.0, 4)
                    multiplier *= src_mult

            # Also check live source trust
            live_trust = self.source_repo.get_current(tenant_id, source)
            if live_trust and live_trust.trust_score != 1.0:
                live_mult = max(self.settings.adaptive_source_trust_min,
                                min(live_trust.trust_score, self.settings.adaptive_source_trust_max))
                adjustments["source_live_trust"] = round(live_mult - 1.0, 4)
                multiplier *= live_mult

        # Category trust multiplier
        if category:
            cat_trust = profile.category_trust_json.get(category)
            if cat_trust is not None:
                cat_mult = max(self.settings.adaptive_weight_min,
                               min(float(cat_trust), self.settings.adaptive_weight_max))
                if cat_mult != 1.0:
                    adjustments["category_trust"] = round(cat_mult - 1.0, 4)
                    multiplier *= cat_mult

        # Weight adjustments
        for factor, weight in profile.weights_json.items():
            w = max(self.settings.adaptive_weight_min,
                    min(float(weight), self.settings.adaptive_weight_max))
            if w != 1.0:
                adjustments[f"weight_{factor}"] = round(w - 1.0, 4)
                multiplier *= w

        # Calibration
        calibration = profile.calibration_json
        if calibration:
            offset = calibration.get("score_offset", 0.0)
            if offset:
                adjustments["calibration_offset"] = offset

        adjusted = base_score * multiplier
        offset = sum(v for k, v in adjustments.items() if "offset" in k)
        adjusted += offset

        # Enforce bounds
        adjusted = max(self.settings.min_score, min(adjusted, self.settings.max_score))
        adjusted = round(adjusted, 4)

        explanation_parts = []
        for key, delta in adjustments.items():
            direction = "+" if delta > 0 else ""
            explanation_parts.append(f"{key}: {direction}{delta:.3f}")
        explanation = "; ".join(explanation_parts) if explanation_parts else "no adjustments"

        # Log
        self.adapt_repo.log_scoring(
            tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
            profile_id=profile.id, base_score=base_score, adjusted_score=adjusted,
            adjustments_json=adjustments, explanation=explanation,
        )

        return {
            "base_score": base_score, "adjusted_score": adjusted,
            "adjustments": adjustments, "explanation": explanation,
            "profile_id": profile.id, "profile_version": profile.version,
        }
