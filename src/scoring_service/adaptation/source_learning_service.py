"""Source Learning / Trust Evolution Engine."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import (
    FeedbackRepository, OutcomeRepository, SourceLearningRepository,
)
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


class SourceLearningService:
    """Gradually evolves source trust based on feedback and outcomes."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.source_repo = SourceLearningRepository(db)
        self.feedback_repo = FeedbackRepository(db)
        self.outcome_repo = OutcomeRepository(db)

    def update_source_trust(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Update trust scores for all sources based on recent outcomes."""
        if not self.settings.source_learning_enabled:
            return []

        alpha = self.settings.source_learning_ewma_alpha
        max_change = self.settings.source_trust_change_max_per_update
        min_samples = self.settings.source_learning_min_samples
        since = datetime.now(timezone.utc) - timedelta(days=30)

        updates = []
        tid = tenant_id or "demo"

        # Get outcomes grouped by source
        outcomes = self.outcome_repo.list_by_tenant(tid, since, limit=1000)
        source_stats: dict[str, dict[str, int]] = {}
        for o in outcomes:
            # Try to identify source from evidence
            src = o.evidence_json.get("source", "unknown")
            if src not in source_stats:
                source_stats[src] = {"confirmed": 0, "rejected": 0, "total": 0, "noise": 0}
            source_stats[src]["total"] += 1
            if o.outcome_type in ("confirmed", "true_positive", "acted_on"):
                source_stats[src]["confirmed"] += 1
            elif o.outcome_type in ("rejected", "false_positive"):
                source_stats[src]["rejected"] += 1
                source_stats[src]["noise"] += 1
            elif o.outcome_type in ("expired", "ignored"):
                source_stats[src]["noise"] += 1

        for source_name, stats in source_stats.items():
            if stats["total"] < min_samples:
                continue

            confirmation_rate = stats["confirmed"] / max(stats["total"], 1)
            noise_rate = stats["noise"] / max(stats["total"], 1)

            current = self.source_repo.get_current(tenant_id, source_name)
            old_trust = current.trust_score if current else 1.0
            old_noise = current.noise_score if current else 0.0
            old_conf = current.confirmation_rate if current else 0.5

            # EWMA update
            new_conf = old_conf * (1 - alpha) + confirmation_rate * alpha
            new_noise = old_noise * (1 - alpha) + noise_rate * alpha

            # Compute new trust: higher confirmation → higher trust, higher noise → lower trust
            raw_trust = new_conf * (1 - new_noise * 0.5)
            trust_delta = raw_trust - old_trust
            # Bound the change
            trust_delta = max(-max_change, min(trust_delta, max_change))
            new_trust = max(
                self.settings.adaptive_source_trust_min,
                min(old_trust + trust_delta, self.settings.adaptive_source_trust_max),
            )

            # Update current trust
            self.source_repo.upsert_current(
                tenant_id=tenant_id, source_name=source_name,
                trust_score=round(new_trust, 4),
                reliability_score=round(new_conf, 4),
                noise_score=round(new_noise, 4),
                confirmation_rate=round(new_conf, 4),
                sample_count=stats["total"],
            )

            # Save history
            reason = None
            if abs(trust_delta) > 0.01:
                direction = "increased" if trust_delta > 0 else "decreased"
                reason = f"Trust {direction} by {abs(trust_delta):.3f}: conf_rate={new_conf:.3f}, noise={new_noise:.3f}"

            self.source_repo.save_history(
                tenant_id=tenant_id, source_name=source_name,
                trust_score=round(new_trust, 4),
                reliability_score=round(new_conf, 4),
                noise_score=round(new_noise, 4),
                timeliness_score=1.0,
                confirmation_rate=round(new_conf, 4),
                sample_count=stats["total"],
                change_reason=reason,
            )

            updates.append({
                "source": source_name, "old_trust": round(old_trust, 4),
                "new_trust": round(new_trust, 4), "delta": round(trust_delta, 4),
                "confirmation_rate": round(new_conf, 4), "noise_score": round(new_noise, 4),
                "samples": stats["total"],
            })

        self.db.commit()
        logger.info("source_learning_updated tenant=%s sources=%d", tenant_id, len(updates))
        return updates

    def get_summary(self, tenant_id: str | None = None) -> dict[str, Any]:
        sources = self.source_repo.list_by_tenant(tenant_id)
        noisy = [s.source_name for s in sources if s.noise_score > 0.4]
        boosted = [s.source_name for s in sources if s.trust_score > 1.2]
        degraded = [s.source_name for s in sources if s.trust_score < 0.6]
        return {
            "tenant_id": tenant_id,
            "total_sources": len(sources),
            "sources": [
                {
                    "source_name": s.source_name, "topic_key": s.topic_key,
                    "trust_score": s.trust_score, "reliability_score": s.reliability_score,
                    "noise_score": s.noise_score, "confirmation_rate": s.confirmation_rate,
                    "sample_count": s.sample_count,
                    "last_updated": s.last_updated.isoformat(),
                }
                for s in sources
            ],
            "noisy_sources": noisy,
            "boosted_sources": boosted,
            "degraded_sources": degraded,
        }
