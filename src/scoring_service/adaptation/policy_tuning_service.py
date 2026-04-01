"""Policy Auto-Tuning Engine — proposes bounded, safe parameter adjustments."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.adaptation.repository import (
    AdaptationRepository, EvaluationRepository, SourceLearningRepository,
)
from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")


class PolicyTuningService:
    """Analyzes evaluation results and proposes bounded policy adjustments."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.adapt_repo = AdaptationRepository(db)
        self.eval_repo = EvaluationRepository(db)
        self.source_repo = SourceLearningRepository(db)

    def generate_proposals(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Analyze latest evaluations and generate adaptation proposals."""
        if not self.settings.adaptation_enabled:
            return []

        proposals = []
        for window in self.settings.evaluation_window_list:
            run = self.eval_repo.get_latest(tenant_id, window)
            if not run or not run.metrics_json:
                continue
            if run.sample_counts:
                total = sum(run.sample_counts.values())
                if total < self.settings.adaptation_min_samples:
                    continue
            proposals.extend(self._analyze_metrics(tenant_id, run))

        # Source-based proposals
        proposals.extend(self._analyze_sources(tenant_id))

        logger.info("proposals_generated tenant=%s count=%d", tenant_id, len(proposals))
        return proposals

    def _analyze_metrics(self, tenant_id: str | None, run) -> list[dict[str, Any]]:
        proposals = []
        metrics = run.metrics_json
        max_delta = self.settings.adaptation_max_delta_per_update

        # High false positive rate → raise alert threshold
        fpr = metrics.get("false_positive_rate")
        if fpr is not None and fpr > 0.3:
            delta = min(fpr * 10, self.settings.adaptive_threshold_delta_max)  # bounded
            proposal = self.adapt_repo.create_proposal(
                tenant_id=tenant_id, proposal_type="threshold",
                target_type="policy", target_id="alert_threshold",
                current_value_json={"false_positive_rate": fpr},
                proposed_value_json={"threshold_increase": round(delta, 2)},
                delta_json={"delta": round(delta, 2)},
                reason=f"High false positive rate ({fpr:.2%}) suggests alert thresholds are too low",
                risk_level="safe" if delta <= 5 else "moderate",
                evaluation_run_id=run.id,
            )
            proposals.append({"proposal_id": proposal.id, "type": "threshold_increase"})

        # Low recommendation usefulness → adjust priority weights
        rec_use = metrics.get("recommendation_usefulness")
        if rec_use is not None and rec_use < 0.4:
            proposal = self.adapt_repo.create_proposal(
                tenant_id=tenant_id, proposal_type="weight",
                target_type="scoring_profile", target_id="recommendation_weights",
                current_value_json={"recommendation_usefulness": rec_use},
                proposed_value_json={"confidence_weight_boost": round(max_delta, 3)},
                delta_json={"delta": round(max_delta, 3)},
                reason=f"Low recommendation usefulness ({rec_use:.2%}) — propose boosting confidence weight",
                risk_level="safe",
                evaluation_run_id=run.id,
            )
            proposals.append({"proposal_id": proposal.id, "type": "weight_adjustment"})

        # High noise rate → strengthen suppression
        noise = metrics.get("noise_rate")
        if noise is not None and noise > 0.4:
            proposal = self.adapt_repo.create_proposal(
                tenant_id=tenant_id, proposal_type="suppression",
                target_type="policy", target_id="noise_suppression",
                current_value_json={"noise_rate": noise},
                proposed_value_json={"suppression_strength_increase": round(min(noise * 0.5, max_delta), 3)},
                delta_json={"delta": round(min(noise * 0.5, max_delta), 3)},
                reason=f"High noise rate ({noise:.2%}) — propose strengthening suppression",
                risk_level="safe" if noise < 0.6 else "moderate",
                evaluation_run_id=run.id,
            )
            proposals.append({"proposal_id": proposal.id, "type": "suppression_tuning"})

        return proposals

    def _analyze_sources(self, tenant_id: str | None) -> list[dict[str, Any]]:
        proposals = []
        sources = self.source_repo.list_by_tenant(tenant_id)
        for src in sources:
            # Noisy source → lower trust
            if src.noise_score > 0.5 and src.sample_count >= self.settings.source_learning_min_samples:
                delta = min(src.noise_score * 0.1, self.settings.source_trust_change_max_per_update)
                proposal = self.adapt_repo.create_proposal(
                    tenant_id=tenant_id, proposal_type="source_trust",
                    target_type="source", target_id=src.source_name,
                    current_value_json={"trust_score": src.trust_score, "noise_score": src.noise_score},
                    proposed_value_json={"trust_score": round(max(src.trust_score - delta, self.settings.adaptive_source_trust_min), 4)},
                    delta_json={"trust_delta": round(-delta, 4)},
                    reason=f"Source '{src.source_name}' has high noise ({src.noise_score:.2f}), "
                           f"samples={src.sample_count}",
                    risk_level="safe",
                )
                proposals.append({"proposal_id": proposal.id, "type": "source_trust_decrease"})

            # Highly reliable source → boost trust
            elif src.confirmation_rate > 0.8 and src.sample_count >= self.settings.source_learning_min_samples:
                delta = min(0.05, self.settings.source_trust_change_max_per_update)
                current = src.trust_score
                new_val = min(current + delta, self.settings.adaptive_source_trust_max)
                if new_val > current:
                    proposal = self.adapt_repo.create_proposal(
                        tenant_id=tenant_id, proposal_type="source_trust",
                        target_type="source", target_id=src.source_name,
                        current_value_json={"trust_score": current, "confirmation_rate": src.confirmation_rate},
                        proposed_value_json={"trust_score": round(new_val, 4)},
                        delta_json={"trust_delta": round(delta, 4)},
                        reason=f"Source '{src.source_name}' has high confirmation rate ({src.confirmation_rate:.2f})",
                        risk_level="safe",
                    )
                    proposals.append({"proposal_id": proposal.id, "type": "source_trust_increase"})

        return proposals

    def approve_proposal(self, proposal_id: int, actor: str = "admin") -> dict[str, Any]:
        proposal = self.adapt_repo.get_proposal(proposal_id)
        if not proposal:
            return {"error": "proposal not found"}
        if proposal.status != "pending":
            return {"error": f"proposal is {proposal.status}, not pending"}
        proposal.status = "approved"
        proposal.approved_by = actor
        proposal.approved_at = datetime.now(timezone.utc)
        self.db.flush()
        return {"status": "approved", "proposal_id": proposal_id}

    def reject_proposal(self, proposal_id: int, actor: str = "admin") -> dict[str, Any]:
        proposal = self.adapt_repo.get_proposal(proposal_id)
        if not proposal:
            return {"error": "proposal not found"}
        if proposal.status != "pending":
            return {"error": f"proposal is {proposal.status}"}
        proposal.status = "rejected"
        proposal.approved_by = actor
        self.db.flush()
        return {"status": "rejected", "proposal_id": proposal_id}

    def apply_proposal(self, proposal_id: int, actor: str = "system") -> dict[str, Any]:
        """Apply an approved proposal to the active profile."""
        proposal = self.adapt_repo.get_proposal(proposal_id)
        if not proposal:
            return {"error": "proposal not found"}
        if proposal.status not in ("approved", "pending"):
            return {"error": f"proposal is {proposal.status}"}

        # Only auto-apply safe changes if mode allows
        if proposal.status == "pending":
            if self.settings.adaptation_mode == "observe_only":
                return {"error": "observe_only mode — cannot apply"}
            if self.settings.adaptation_mode == "suggest_only":
                return {"error": "suggest_only mode — approve first"}
            if proposal.risk_level != "safe" and self.settings.adaptation_mode != "auto_safe_with_audit":
                return {"error": f"risky proposal requires approval (risk={proposal.risk_level})"}

        profile = self.adapt_repo.get_active_profile(proposal.tenant_id)
        if not profile:
            # Create default profile
            profile = self.adapt_repo.create_profile(
                tenant_id=proposal.tenant_id, name="default", is_active=True,
            )

        # Save current version before applying
        self.adapt_repo.save_version(
            profile_id=profile.id, version=profile.version,
            snapshot_json={
                "weights": profile.weights_json,
                "source_trust": profile.source_trust_json,
                "category_trust": profile.category_trust_json,
                "thresholds": profile.thresholds_json,
                "calibration": profile.calibration_json,
            },
            proposal_id=proposal_id,
            change_summary=proposal.reason,
        )

        # Apply changes based on proposal type
        proposed = proposal.proposed_value_json
        if proposal.proposal_type == "source_trust" and proposal.target_type == "source":
            new_trust = proposed.get("trust_score", profile.source_trust_json.get(proposal.target_id, 1.0))
            profile.source_trust_json = {**profile.source_trust_json, proposal.target_id: new_trust}
        elif proposal.proposal_type == "weight":
            for key, val in proposed.items():
                profile.weights_json = {**profile.weights_json, key: val}
        elif proposal.proposal_type == "threshold":
            for key, val in proposed.items():
                profile.thresholds_json = {**profile.thresholds_json, key: val}
        elif proposal.proposal_type == "suppression":
            for key, val in proposed.items():
                profile.calibration_json = {**profile.calibration_json, key: val}

        profile.version += 1
        proposal.status = "applied"
        proposal.applied_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info(
            "proposal_applied id=%s type=%s target=%s new_version=%d",
            proposal_id, proposal.proposal_type, proposal.target_id, profile.version,
        )
        return {
            "status": "applied", "proposal_id": proposal_id,
            "profile_id": profile.id, "new_version": profile.version,
        }

    def simulate_proposal(self, proposal_id: int) -> dict[str, Any]:
        """Simulate what a proposal would change (dry-run)."""
        proposal = self.adapt_repo.get_proposal(proposal_id)
        if not proposal:
            return {"error": "proposal not found"}
        return {
            "proposal_id": proposal_id,
            "type": proposal.proposal_type,
            "target": f"{proposal.target_type}/{proposal.target_id}",
            "current": proposal.current_value_json,
            "proposed": proposal.proposed_value_json,
            "delta": proposal.delta_json,
            "risk_level": proposal.risk_level,
            "reason": proposal.reason,
            "dry_run": True,
        }
