"""Seed demo data for adaptation system."""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import (
    AdaptiveScoringProfile, FeedbackEvent, GoalDefinition, OutcomeRecord,
    SourceTrustCurrent,
)

logger = logging.getLogger("scoring_service")


def seed_adaptation_demo(db: Session, settings: Settings) -> dict:
    """Seed demo adaptation data."""
    tenant_id = settings.demo_tenant_id
    now = datetime.now(timezone.utc)
    stats = {"feedback": 0, "outcomes": 0, "goals": 0, "profiles": 0, "sources": 0}

    # Check if already seeded
    existing = db.query(FeedbackEvent).filter(FeedbackEvent.tenant_id == tenant_id).first()
    if existing:
        return {"status": "already_seeded"}

    # ── Feedback events ──
    target_types = ["trend", "recommendation", "alert"]
    labels_map = {
        "trend": ["relevant", "noise", "relevant", "relevant", "noise"],
        "recommendation": ["useful", "useless", "useful", "useful", "late"],
        "alert": ["true_positive", "false_positive", "true_positive", "true_positive", "false_positive"],
    }
    for target_type in target_types:
        for i in range(30):
            db.add(FeedbackEvent(
                tenant_id=tenant_id, target_type=target_type, target_id=i + 1,
                feedback_type="relevance" if target_type == "trend" else "usefulness",
                label=random.choice(labels_map[target_type]),
                score=round(random.uniform(0.3, 0.95), 2),
                usefulness_rating=random.randint(1, 5),
                reviewer="demo_user", source="human",
                metadata_json={"demo": True},
                created_at=now - timedelta(hours=random.randint(1, 168)),
            ))
            stats["feedback"] += 1

    # ── Outcome records ──
    outcome_map = {
        "trend": ["confirmed", "rejected", "confirmed", "confirmed", "expired"],
        "recommendation": ["acted_on", "ignored", "acted_on", "acted_on", "ignored"],
        "alert": ["true_positive", "false_positive", "true_positive", "confirmed", "false_positive"],
    }
    for entity_type in ["trend", "recommendation", "alert"]:
        for i in range(25):
            db.add(OutcomeRecord(
                tenant_id=tenant_id, entity_type=entity_type, entity_id=i + 1,
                outcome_type=random.choice(outcome_map[entity_type]),
                confidence=round(random.uniform(0.5, 0.95), 2),
                evidence_json={"source": random.choice(["rss", "reddit", "api"]), "demo": True},
                created_at=now - timedelta(hours=random.randint(1, 168)),
            ))
            stats["outcomes"] += 1

    # ── Adaptive scoring profile ──
    profile = AdaptiveScoringProfile(
        tenant_id=tenant_id, name="default", is_active=True, version=1,
        weights_json={"confidence": 1.1, "growth_rate": 1.05},
        source_trust_json={"rss": 1.0, "reddit": 0.95, "api": 1.1},
        category_trust_json={"technology": 1.1, "marketing": 1.0, "business": 0.95},
        thresholds_json={"alert_min_score": 50.0, "recommendation_min_confidence": 0.6},
        calibration_json={"score_offset": 0.0},
        safe_bounds_json={"weight_min": 0.1, "weight_max": 3.0, "trust_min": 0.1, "trust_max": 2.0},
        created_by="seed",
    )
    db.add(profile)
    stats["profiles"] += 1

    # ── Goals ──
    goals = [
        {"name": "Maximize useful recommendations", "target_metric": "recommendation_usefulness",
         "direction": "maximize", "target_value": 0.8, "evaluation_window": "7d"},
        {"name": "Minimize false positive alerts", "target_metric": "false_positive_rate",
         "direction": "minimize", "target_value": 0.15, "evaluation_window": "7d"},
        {"name": "Improve trend confirmation", "target_metric": "trend_confirmation_rate",
         "direction": "maximize", "target_value": 0.7, "evaluation_window": "7d"},
    ]
    for g in goals:
        db.add(GoalDefinition(
            tenant_id=tenant_id, **g,
            guardrails_json={"alert_precision": {"min": 0.5}},
            adaptation_strategy="conservative", approval_mode="suggest_only",
        ))
        stats["goals"] += 1

    # ── Source trust ──
    for src in ["rss", "reddit", "api", "twitter"]:
        db.add(SourceTrustCurrent(
            tenant_id=tenant_id, source_name=src, topic_key="__global__",
            trust_score=round(random.uniform(0.7, 1.3), 3),
            reliability_score=round(random.uniform(0.6, 0.95), 3),
            noise_score=round(random.uniform(0.05, 0.4), 3),
            timeliness_score=round(random.uniform(0.7, 1.0), 3),
            confirmation_rate=round(random.uniform(0.5, 0.9), 3),
            sample_count=random.randint(15, 100),
        ))
        stats["sources"] += 1

    db.commit()
    logger.info("adaptation_demo_seeded stats=%s", stats)
    return {"status": "seeded", **stats}
