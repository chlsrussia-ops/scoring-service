"""Rollback service — safely reverts applied adaptations."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import AdaptationRepository, QualityRepository
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


class RollbackService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.adapt_repo = AdaptationRepository(db)
        self.quality_repo = QualityRepository(db)

    def rollback_proposal(self, proposal_id: int, reason: str, actor: str = "system") -> dict[str, Any]:
        """Rollback an applied proposal by reverting the profile to its previous version."""
        proposal = self.adapt_repo.get_proposal(proposal_id)
        if not proposal:
            return {"error": "proposal not found"}
        if proposal.status != "applied":
            return {"error": f"proposal is {proposal.status}, not applied"}

        # Find the profile
        profile = self.adapt_repo.get_active_profile(proposal.tenant_id)
        if not profile:
            return {"error": "no active profile"}

        # Find the version before this proposal was applied
        target_version = profile.version - 1
        if target_version < 1:
            return {"error": "no previous version to rollback to"}

        version_snapshot = self.adapt_repo.get_version(profile.id, target_version)
        if not version_snapshot:
            return {"error": f"version {target_version} snapshot not found"}

        # Capture current metrics for audit
        metrics_before = {
            "weights": profile.weights_json,
            "source_trust": profile.source_trust_json,
            "thresholds": profile.thresholds_json,
        }

        # Restore from snapshot
        snap = version_snapshot.snapshot_json
        profile.weights_json = snap.get("weights", {})
        profile.source_trust_json = snap.get("source_trust", {})
        profile.category_trust_json = snap.get("category_trust", {})
        profile.thresholds_json = snap.get("thresholds", {})
        profile.calibration_json = snap.get("calibration", {})
        profile.version += 1  # increment version even on rollback for audit trail

        proposal.status = "rolled_back"
        proposal.rolled_back_at = datetime.now(timezone.utc)

        # Record rollback
        rollback = self.adapt_repo.create_rollback(
            proposal_id=proposal_id, profile_id=profile.id,
            from_version=profile.version - 1, to_version=profile.version,
            reason=reason, rolled_back_by=actor,
            metrics_before_json=metrics_before,
            metrics_after_json=snap,
        )

        # Self-evaluation report
        self.quality_repo.save_report(
            tenant_id=proposal.tenant_id, report_type="rollback",
            entity_type="proposal", entity_id=proposal_id,
            summary=f"Rolled back proposal #{proposal_id}: {reason}",
            details_json={"proposal": proposal.proposal_type, "target": proposal.target_id},
            metrics_before_json=metrics_before, metrics_after_json=snap,
            explanation=reason,
        )

        self.db.flush()
        logger.info("rollback_executed proposal_id=%s actor=%s reason=%s", proposal_id, actor, reason)

        return {
            "status": "rolled_back", "proposal_id": proposal_id,
            "rollback_id": rollback.id, "profile_version": profile.version,
            "reason": reason,
        }

    def auto_rollback_if_degraded(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Check if any recently applied proposals caused degradation and rollback."""
        if not self.settings.adaptation_rollback_on_degradation:
            return []

        from scoring_service.adaptation.repository import EvaluationRepository
        eval_repo = EvaluationRepository(self.db)
        latest = eval_repo.get_latest(tenant_id, "24h")
        if not latest or not latest.degradation_flags:
            return []

        # Find recently applied proposals
        applied = self.adapt_repo.list_proposals(tenant_id, status="applied", limit=5)
        rollbacks = []
        for proposal in applied:
            if proposal.applied_at and (datetime.now(timezone.utc) - proposal.applied_at).total_seconds() < 86400:
                result = self.rollback_proposal(
                    proposal.id,
                    reason=f"Auto-rollback: degradation detected in {', '.join(latest.degradation_flags)}",
                    actor="auto_rollback",
                )
                if "error" not in result:
                    rollbacks.append(result)

        return rollbacks
