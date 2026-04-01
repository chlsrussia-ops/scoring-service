"""Usage metering + quota enforcement service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.db.models import (
    PlanDefinition,
    QuotaEnforcementLog,
    Tenant,
    UsageCounter,
)


# Default plan limits
DEFAULT_PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "limits": {
            "events_per_month": 1000,
            "analysis_runs_per_month": 10,
            "notifications_per_month": 50,
            "api_clients": 2,
        },
        "features": ["basic_detection", "log_notifications"],
    },
    "pro": {
        "name": "Pro",
        "limits": {
            "events_per_month": 50000,
            "analysis_runs_per_month": 500,
            "notifications_per_month": 5000,
            "api_clients": 10,
        },
        "features": ["basic_detection", "spike_detection", "webhook_notifications", "exports"],
    },
    "team": {
        "name": "Team",
        "limits": {
            "events_per_month": 500000,
            "analysis_runs_per_month": 5000,
            "notifications_per_month": 50000,
            "api_clients": 50,
        },
        "features": ["basic_detection", "spike_detection", "webhook_notifications", "exports", "custom_policies", "backfill"],
    },
    "internal": {
        "name": "Internal",
        "limits": {
            "events_per_month": 999999999,
            "analysis_runs_per_month": 999999999,
            "notifications_per_month": 999999999,
            "api_clients": 999,
        },
        "features": ["all"],
    },
}


class UsageService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current_period(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def increment(self, tenant_id: str, metric: str, count: int = 1) -> UsageCounter:
        period = self.get_current_period()
        counter = (
            self.db.query(UsageCounter)
            .filter(
                UsageCounter.tenant_id == tenant_id,
                UsageCounter.metric == metric,
                UsageCounter.period == period,
            )
            .first()
        )
        if counter:
            counter.count += count  # type: ignore[assignment]
        else:
            counter = UsageCounter(
                tenant_id=tenant_id,
                metric=metric,
                period=period,
                count=count,
            )
            self.db.add(counter)
        self.db.commit()
        self.db.refresh(counter)
        return counter

    def get_usage(self, tenant_id: str, period: str | None = None) -> dict[str, int]:
        p = period or self.get_current_period()
        counters = (
            self.db.query(UsageCounter)
            .filter(
                UsageCounter.tenant_id == tenant_id,
                UsageCounter.period == p,
            )
            .all()
        )
        return {c.metric: c.count for c in counters}

    def get_plan_limits(self, tenant_id: str) -> dict[str, int]:
        tenant = self.db.get(Tenant, tenant_id)
        plan_id = tenant.plan if tenant else "free"

        plan = self.db.get(PlanDefinition, plan_id)
        if plan:
            return plan.limits_json

        default = DEFAULT_PLANS.get(plan_id, DEFAULT_PLANS["free"])
        return default["limits"]

    def check_quota(
        self, tenant_id: str, metric: str, increment: int = 1,
    ) -> dict[str, Any]:
        """Check if tenant can perform the action. Returns enforcement result."""
        usage = self.get_usage(tenant_id)
        limits = self.get_plan_limits(tenant_id)
        current = usage.get(metric, 0)
        limit_val = limits.get(metric, 999999999)
        projected = current + increment

        if projected > limit_val:
            # Hard block
            self._log_enforcement(tenant_id, metric, current, limit_val, "block")
            return {
                "allowed": False,
                "metric": metric,
                "current": current,
                "limit": limit_val,
                "status": "exceeded",
                "action": "block",
            }

        if projected > limit_val * 0.8:
            # Soft warning
            self._log_enforcement(tenant_id, metric, current, limit_val, "warn")
            return {
                "allowed": True,
                "metric": metric,
                "current": current,
                "limit": limit_val,
                "status": "warning",
                "action": "warn",
            }

        return {
            "allowed": True,
            "metric": metric,
            "current": current,
            "limit": limit_val,
            "status": "ok",
            "action": "none",
        }

    def get_summary(self, tenant_id: str) -> dict[str, Any]:
        usage = self.get_usage(tenant_id)
        limits = self.get_plan_limits(tenant_id)
        tenant = self.db.get(Tenant, tenant_id)
        plan = tenant.plan if tenant else "free"

        warnings: list[str] = []
        quotas: list[dict[str, Any]] = []
        for metric, limit_val in limits.items():
            current = usage.get(metric, 0)
            pct = (current / limit_val * 100) if limit_val > 0 else 0
            status = "ok"
            if pct >= 100:
                status = "exceeded"
                warnings.append(f"{metric}: exceeded ({current}/{limit_val})")
            elif pct >= 80:
                status = "warning"
                warnings.append(f"{metric}: approaching limit ({current}/{limit_val})")
            quotas.append({
                "metric": metric,
                "current": current,
                "limit": limit_val,
                "usage_pct": round(pct, 1),
                "status": status,
            })

        return {
            "tenant_id": tenant_id,
            "period": self.get_current_period(),
            "plan": plan,
            "metrics": usage,
            "limits": limits,
            "quotas": quotas,
            "warnings": warnings,
        }

    def _log_enforcement(
        self, tenant_id: str, metric: str, current: int, limit_val: int, action: str,
    ) -> None:
        log = QuotaEnforcementLog(
            tenant_id=tenant_id,
            metric=metric,
            current_value=current,
            limit_value=limit_val,
            action=action,
        )
        self.db.add(log)
        self.db.commit()

    def seed_plans(self) -> None:
        """Seed default plan definitions."""
        for plan_id, plan_data in DEFAULT_PLANS.items():
            existing = self.db.get(PlanDefinition, plan_id)
            if not existing:
                plan = PlanDefinition(
                    id=plan_id,
                    name=plan_data["name"],
                    limits_json=plan_data["limits"],
                    features_json=plan_data["features"],
                )
                self.db.add(plan)
        self.db.commit()
