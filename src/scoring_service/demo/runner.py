"""Demo runner - orchestrates seed, sync, analyze, LLM, alerts."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import (
    Alert, DataSource, DemoRun, PipelineEvent, Recommendation,
    Signal, SourceType, Tenant, Trend, Workspace,
)
from scoring_service.demo.seed_data import (
    generate_alerts, generate_demo_sources, generate_events,
    generate_recommendations, generate_trends,
)

logger = logging.getLogger("scoring_service")


class DemoRunner:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.tenant_id = settings.demo_tenant_id
        self.workspace_id = settings.demo_workspace_id

    def _log_run(self, action: str, status: str = "running", result: dict | None = None, error: str | None = None) -> DemoRun:
        run = DemoRun(
            tenant_id=self.tenant_id,
            action=action,
            status=status,
            result_json=result or {},
            error=error,
            completed_at=datetime.now(timezone.utc) if status != "running" else None,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def ensure_tenant(self) -> None:
        """Ensure demo tenant and workspace exist."""
        tenant = self.db.query(Tenant).filter(Tenant.id == self.tenant_id).first()
        if not tenant:
            tenant = Tenant(
                id=self.tenant_id,
                name="TrendIntel Demo",
                slug="demo",
                plan="pro",
                settings_json={"demo": True},
            )
            self.db.add(tenant)
            self.db.commit()

        ws = self.db.query(Workspace).filter(Workspace.id == self.workspace_id).first()
        if not ws:
            ws = Workspace(
                id=self.workspace_id,
                tenant_id=self.tenant_id,
                name="Default Workspace",
                slug="default",
                is_default=True,
            )
            self.db.add(ws)
            self.db.commit()

    def seed(self) -> dict[str, Any]:
        """Seed demo data: events, trends, recommendations, alerts, sources."""
        self.ensure_tenant()
        now = datetime.now(timezone.utc)

        # Seed pipeline events
        events_data = generate_events(1200)
        event_count = 0
        for ev in events_data:
            existing = self.db.query(PipelineEvent).filter(
                PipelineEvent.tenant_id == self.tenant_id,
                PipelineEvent.external_id == ev["external_id"],
            ).first()
            if existing:
                continue
            pe = PipelineEvent(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                source=ev["source_name"],
                event_type=ev["source_type"],
                external_id=ev["external_id"],
                payload_json=ev,
                normalized_json={
                    "title": ev["title"],
                    "body": ev["body"],
                    "url": ev["url"],
                    "category": ev["category"],
                    "tags": ev["tags"],
                    "metrics": ev["metrics"],
                    "published_at": ev["published_at"],
                },
            )
            self.db.add(pe)
            event_count += 1
        self.db.commit()

        # Seed trends
        trends_data = generate_trends()
        trend_map: dict[str, int] = {}
        trend_count = 0
        for td in trends_data:
            existing = self.db.query(Trend).filter(
                Trend.tenant_id == self.tenant_id,
                Trend.topic == td["topic"],
            ).first()
            if existing:
                trend_map[td["topic"]] = existing.id
                continue
            t = Trend(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                source=td["source"],
                category=td["category"],
                topic=td["topic"],
                score=td["score"],
                confidence=td["confidence"],
                direction=td["direction"],
                event_count=td["event_count"],
                growth_rate=td["growth_rate"],
                metadata_json={"scenario": td.get("scenario", "")},
            )
            self.db.add(t)
            self.db.flush()
            trend_map[td["topic"]] = t.id
            trend_count += 1
        self.db.commit()

        # Seed recommendations
        recs_data = generate_recommendations(trends_data)
        rec_count = 0
        for rd in recs_data:
            existing = self.db.query(Recommendation).filter(
                Recommendation.tenant_id == self.tenant_id,
                Recommendation.title == rd["title"],
            ).first()
            if existing:
                continue
            # Try to find linked trend
            linked_trend_id = None
            for t_topic, t_id in trend_map.items():
                if t_topic.lower() in rd['title'].lower() or t_topic.lower() in rd.get('body','').lower():
                    linked_trend_id = t_id
                    break
            r = Recommendation(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                trend_id=linked_trend_id,
                category=rd["category"],
                title=rd["title"],
                body=rd["body"],
                priority=rd["priority"],
                confidence=rd["confidence"],
            )
            self.db.add(r)
            rec_count += 1
        self.db.commit()

        # Seed alerts
        alerts_data = generate_alerts(trends_data)
        alert_count = 0
        for ad in alerts_data:
            existing = self.db.query(Alert).filter(
                Alert.tenant_id == self.tenant_id,
                Alert.title == ad["title"],
            ).first()
            if existing:
                continue
            # Try to find linked trend
            alert_trend_id = None
            for t_topic, t_id in trend_map.items():
                if t_topic.lower() in ad['title'].lower():
                    alert_trend_id = t_id
                    break
            a = Alert(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                trend_id=alert_trend_id,
                alert_type=ad["alert_type"],
                severity=ad["severity"],
                title=ad["title"],
                body=ad["body"],
                status=ad["status"],
            )
            self.db.add(a)
            alert_count += 1
        self.db.commit()

        # Seed data sources
        sources_data = generate_demo_sources()
        source_count = 0
        for sd in sources_data:
            existing = self.db.query(DataSource).filter(
                DataSource.tenant_id == self.tenant_id,
                DataSource.name == sd["name"],
            ).first()
            if existing:
                continue
            ds = DataSource(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                name=sd["name"],
                source_type=sd["source_type"],
                config_json=sd["config_json"],
            )
            self.db.add(ds)
            source_count += 1
        self.db.commit()

        result = {
            "events": event_count,
            "trends": trend_count,
            "recommendations": rec_count,
            "alerts": alert_count,
            "sources": source_count,
        }
        self._log_run("seed", "completed", result)
        return result

    async def run_analysis(self) -> dict[str, Any]:
        """Run trend detection analysis on pipeline events."""
        events = self.db.query(PipelineEvent).filter(
            PipelineEvent.tenant_id == self.tenant_id,
        ).all()

        # Simple trend detection: group by category, count, score
        category_counts: dict[str, list] = {}
        for ev in events:
            cat = (ev.normalized_json or {}).get("category", "general")
            if cat not in category_counts:
                category_counts[cat] = []
            category_counts[cat].append(ev)

        new_signals = 0
        for cat, evs in category_counts.items():
            sig = Signal(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                source="analysis",
                category=cat,
                topic=cat.replace("_", " ").title(),
                value=float(len(evs)),
                metadata_json={"event_count": len(evs)},
            )
            self.db.add(sig)
            new_signals += 1
        self.db.commit()

        result = {"categories_analyzed": len(category_counts), "signals_created": new_signals, "events_processed": len(events)}
        self._log_run("analysis", "completed", result)
        return result

    async def generate_ai(self) -> dict[str, Any]:
        """Generate LLM narratives for all trends and recommendations."""
        from scoring_service.llm.service import LlmService
        llm = LlmService(self.db, self.settings)
        result = await llm.generate_all_narratives(self.tenant_id)
        self._log_run("generate_ai", "completed", result)
        return result

    async def dispatch_alerts(self) -> dict[str, Any]:
        """Mark alerts as dispatched (demo mode)."""
        alerts = self.db.query(Alert).filter(
            Alert.tenant_id == self.tenant_id,
            Alert.status == "open",
        ).all()
        dispatched = 0
        for a in alerts:
            a.status = "dispatched"
            dispatched += 1
        self.db.commit()
        result = {"dispatched": dispatched}
        self._log_run("dispatch_alerts", "completed", result)
        return result

    async def run_all(self) -> dict[str, Any]:
        """Full demo pipeline: seed -> analyze -> generate AI -> dispatch alerts."""
        seed_result = self.seed()
        analysis_result = await self.run_analysis()
        ai_result = await self.generate_ai()
        alert_result = await self.dispatch_alerts()

        result = {
            "seed": seed_result,
            "analysis": analysis_result,
            "ai": ai_result,
            "alerts": alert_result,
        }
        self._log_run("run_all", "completed", result)
        return result

    def get_status(self) -> dict[str, Any]:
        """Get current demo environment status."""
        events = self.db.query(PipelineEvent).filter(PipelineEvent.tenant_id == self.tenant_id).count()
        trends = self.db.query(Trend).filter(Trend.tenant_id == self.tenant_id).count()
        recs = self.db.query(Recommendation).filter(Recommendation.tenant_id == self.tenant_id).count()
        alerts = self.db.query(Alert).filter(Alert.tenant_id == self.tenant_id).count()
        sources = self.db.query(DataSource).filter(DataSource.tenant_id == self.tenant_id).count()

        recent_runs = self.db.query(DemoRun).filter(
            DemoRun.tenant_id == self.tenant_id,
        ).order_by(DemoRun.started_at.desc()).limit(10).all()

        return {
            "tenant_id": self.tenant_id,
            "events": events,
            "trends": trends,
            "recommendations": recs,
            "alerts": alerts,
            "sources": sources,
            "recent_runs": [
                {"id": r.id, "action": r.action, "status": r.status, "started_at": str(r.started_at), "result": r.result_json}
                for r in recent_runs
            ],
        }
