"""Policy CRUD + evaluation service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.db.models import (
    PolicyBundle, PolicyStatus, PolicyType, PolicyVersion,
)
from scoring_service.policies.engine import evaluate_policy_rules


class PolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_bundle(
        self,
        *,
        tenant_id: str | None,
        workspace_id: str | None = None,
        name: str,
        policy_type: str,
        description: str | None = None,
        is_global: bool = False,
        priority: int = 100,
        config: dict[str, Any],
    ) -> PolicyBundle:
        bundle = PolicyBundle(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
            policy_type=PolicyType(policy_type),
            description=description,
            is_global=is_global,
            priority=priority,
        )
        self.db.add(bundle)
        self.db.flush()

        version = PolicyVersion(
            bundle_id=bundle.id,
            version=1,
            config_json=config,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(bundle)
        return bundle

    def get_bundle(self, bundle_id: int) -> PolicyBundle | None:
        return self.db.get(PolicyBundle, bundle_id)

    def list_bundles(
        self,
        tenant_id: str | None = None,
        policy_type: str | None = None,
        *,
        include_global: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PolicyBundle]:
        q = self.db.query(PolicyBundle)
        if tenant_id:
            if include_global:
                q = q.filter(
                    (PolicyBundle.tenant_id == tenant_id) | (PolicyBundle.is_global == True)
                )
            else:
                q = q.filter(PolicyBundle.tenant_id == tenant_id)
        if policy_type:
            q = q.filter(PolicyBundle.policy_type == PolicyType(policy_type))
        return q.order_by(PolicyBundle.priority, PolicyBundle.id).offset(offset).limit(limit).all()

    def activate_version(self, bundle_id: int, version_id: int | None = None) -> PolicyVersion | None:
        bundle = self.db.get(PolicyBundle, bundle_id)
        if not bundle:
            return None

        # Deactivate all versions
        for v in bundle.versions:
            v.is_active = False  # type: ignore[assignment]

        # Activate latest or specific version
        if version_id:
            target = self.db.get(PolicyVersion, version_id)
        else:
            target = (
                self.db.query(PolicyVersion)
                .filter(PolicyVersion.bundle_id == bundle_id)
                .order_by(PolicyVersion.version.desc())
                .first()
            )
        if target:
            target.is_active = True  # type: ignore[assignment]
            target.activated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            bundle.status = PolicyStatus.active  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(target)
        return target

    def deactivate_bundle(self, bundle_id: int) -> PolicyBundle | None:
        bundle = self.db.get(PolicyBundle, bundle_id)
        if not bundle:
            return None
        bundle.status = PolicyStatus.inactive  # type: ignore[assignment]
        for v in bundle.versions:
            v.is_active = False  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(bundle)
        return bundle

    def add_version(self, bundle_id: int, config: dict[str, Any]) -> PolicyVersion | None:
        bundle = self.db.get(PolicyBundle, bundle_id)
        if not bundle:
            return None
        max_ver = max((v.version for v in bundle.versions), default=0)
        version = PolicyVersion(
            bundle_id=bundle_id,
            version=max_ver + 1,
            config_json=config,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_active_version(self, bundle_id: int) -> PolicyVersion | None:
        return (
            self.db.query(PolicyVersion)
            .filter(PolicyVersion.bundle_id == bundle_id, PolicyVersion.is_active == True)
            .first()
        )

    def get_effective_policies(
        self,
        tenant_id: str,
        policy_type: str,
        workspace_id: str | None = None,
    ) -> list[tuple[PolicyBundle, PolicyVersion]]:
        """Get active policies ordered by precedence:
        workspace > tenant > global."""
        q = (
            self.db.query(PolicyBundle, PolicyVersion)
            .join(PolicyVersion, PolicyVersion.bundle_id == PolicyBundle.id)
            .filter(
                PolicyVersion.is_active == True,
                PolicyBundle.status == PolicyStatus.active,
                PolicyBundle.policy_type == PolicyType(policy_type),
            )
            .filter(
                (PolicyBundle.tenant_id == tenant_id) | (PolicyBundle.is_global == True)
            )
        )
        results = q.order_by(PolicyBundle.priority).all()

        # Sort: workspace-specific > tenant-specific > global
        def precedence(pair: tuple[PolicyBundle, PolicyVersion]) -> int:
            b = pair[0]
            if workspace_id and b.workspace_id == workspace_id:
                return 0
            if b.tenant_id == tenant_id and not b.is_global:
                return 1
            return 2

        return sorted(results, key=precedence)

    def evaluate(
        self,
        tenant_id: str,
        policy_type: str,
        data: dict[str, Any],
        workspace_id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Evaluate data against effective policies."""
        policies = self.get_effective_policies(tenant_id, policy_type, workspace_id)
        all_matched: list[dict[str, Any]] = []
        all_actions: list[str] = []
        all_weights: dict[str, float] = {}
        policy_version_id: int | None = None

        for bundle, version in policies:
            config = version.config_json or {}
            rules = config.get("rules", [])
            matched = evaluate_policy_rules(data, rules)
            if matched:
                policy_version_id = version.id
                for m in matched:
                    m["policy_name"] = bundle.name
                    m["policy_version"] = version.version
                all_matched.extend(matched)
                all_actions.extend(m["action"] for m in matched)

            weights = config.get("weights", {})
            all_weights.update(weights)

        return {
            "matched_rules": all_matched,
            "actions": list(set(all_actions)),
            "weights": all_weights,
            "policy_version_id": policy_version_id,
            "dry_run": dry_run,
        }
