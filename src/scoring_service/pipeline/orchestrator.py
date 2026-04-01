"""Pipeline orchestrator — runs ingestion > normalization > detection > scoring > recommendation > alerting."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.db.models import (
    Alert,
    BackfillRequest,
    PipelineEvent,
    ProcessingCheckpoint,
    ProcessingRun,
    ProcessingStage,
    RebuildRequest,
    Recommendation,
    RunStatus,
    Signal,
    SignalLineageLink,
    Trend,
    TrendEvidence,
    DecisionTrace,
)
from scoring_service.plugins.registry import PluginRegistry

logger = logging.getLogger("scoring_service.pipeline")

STAGES = ["ingestion", "normalization", "detection", "scoring", "recommendation", "alerting"]


class PipelineOrchestrator:
    def __init__(self, db: Session, registry: PluginRegistry) -> None:
        self.db = db
        self.registry = registry

    def run(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        source_filter: str | None = None,
        run_type: str = "manual",
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        detector_name: str = "threshold",
        scorer_name: str = "default",
        recommender_name: str = "top_n",
        notifier_name: str = "log",
        source_name: str = "demo",
        context: dict[str, Any] | None = None,
        policy_eval_result: dict[str, Any] | None = None,
    ) -> ProcessingRun:
        """Execute full pipeline for a tenant."""
        now = datetime.now(timezone.utc)
        run = ProcessingRun(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            run_type=run_type,
            status=RunStatus.running,
            source_filter=source_filter,
            window_start=window_start or now,
            window_end=window_end or now,
            started_at=now,
        )
        self.db.add(run)
        self.db.flush()

        stages: dict[str, ProcessingStage] = {}
        for stage_name in STAGES:
            stage = ProcessingStage(run_id=run.id, stage_name=stage_name)
            self.db.add(stage)
            stages[stage_name] = stage
        self.db.flush()

        stats: dict[str, Any] = {}
        ctx = context or {}
        weights = {}
        policy_version_id: int | None = None
        if policy_eval_result:
            weights = policy_eval_result.get("weights", {})
            policy_version_id = policy_eval_result.get("policy_version_id")

        try:
            # 1. INGESTION
            raw_events = self._stage_ingest(
                stages["ingestion"], tenant_id, workspace_id,
                source_name, source_filter,
            )
            stats["events_ingested"] = len(raw_events)

            # 2. NORMALIZATION
            normalized = self._stage_normalize(stages["normalization"], raw_events)
            stats["events_normalized"] = len(normalized)

            # 3. DETECTION
            detected = self._stage_detect(
                stages["detection"], normalized, detector_name, ctx,
            )
            stats["trends_detected"] = len(detected)

            # 4. SCORING
            scored = self._stage_score(
                stages["scoring"], detected, scorer_name, weights,
            )
            stats["trends_scored"] = len(scored)

            # 5. SAVE trends + signals + create lineage
            saved_trends = self._save_trends(
                tenant_id, workspace_id, scored, run.id, policy_version_id,
            )
            stats["trends_saved"] = len(saved_trends)

            # 6. RECOMMENDATION
            recs = self._stage_recommend(
                stages["recommendation"], scored, recommender_name, ctx,
            )
            saved_recs = self._save_recommendations(
                tenant_id, workspace_id, recs, saved_trends, run.id,
            )
            stats["recommendations_created"] = len(saved_recs)

            # 7. ALERTING
            alerts_created = self._stage_alert(
                stages["alerting"], saved_trends, tenant_id, workspace_id,
                notifier_name, run.id,
            )
            stats["alerts_created"] = alerts_created

            run.status = RunStatus.completed  # type: ignore[assignment]
            run.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            run.stats_json = stats  # type: ignore[assignment]

        except Exception as e:
            logger.exception("Pipeline run %d failed: %s", run.id, e)
            run.status = RunStatus.failed  # type: ignore[assignment]
            run.error_message = str(e)  # type: ignore[assignment]
            run.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            run.stats_json = stats  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(run)
        return run

    def _stage_ingest(
        self, stage: ProcessingStage, tenant_id: str, workspace_id: str | None,
        source_name: str, source_filter: str | None,
    ) -> list[dict[str, Any]]:
        stage.status = RunStatus.running  # type: ignore[assignment]
        stage.started_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        provider = self.registry.get_source(source_name)
        if not provider:
            stage.status = RunStatus.failed  # type: ignore[assignment]
            stage.error_message = f"Source provider '{source_name}' not found"  # type: ignore[assignment]
            stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            return []

        raw_events = provider.fetch(limit=100)
        stage.items_in = len(raw_events)  # type: ignore[assignment]

        # Persist events
        for raw in raw_events:
            evt = PipelineEvent(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source=raw.get("source", source_name),
                event_type=raw.get("event_type", "generic"),
                external_id=raw.get("external_id"),
                payload_json=raw,
            )
            self.db.add(evt)

        stage.items_out = len(raw_events)  # type: ignore[assignment]
        stage.status = RunStatus.completed  # type: ignore[assignment]
        stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        self.db.flush()
        return raw_events

    def _stage_normalize(
        self, stage: ProcessingStage, raw_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        stage.status = RunStatus.running  # type: ignore[assignment]
        stage.started_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        stage.items_in = len(raw_events)  # type: ignore[assignment]

        normalizer = self.registry.get_normalizer("default")
        if not normalizer:
            stage.status = RunStatus.completed  # type: ignore[assignment]
            stage.items_out = len(raw_events)  # type: ignore[assignment]
            stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            return raw_events

        normalized = []
        for raw in raw_events:
            try:
                normalized.append(normalizer.normalize(raw))
            except Exception:
                stage.items_error = (stage.items_error or 0) + 1  # type: ignore[assignment]
                normalized.append(raw)

        stage.items_out = len(normalized)  # type: ignore[assignment]
        stage.status = RunStatus.completed  # type: ignore[assignment]
        stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        return normalized

    def _stage_detect(
        self, stage: ProcessingStage, items: list[dict[str, Any]],
        detector_name: str, context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        stage.status = RunStatus.running  # type: ignore[assignment]
        stage.started_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        stage.items_in = len(items)  # type: ignore[assignment]

        detector = self.registry.get_detector(detector_name)
        if not detector:
            detector = self.registry.get_detector("threshold")
        if not detector:
            stage.status = RunStatus.failed  # type: ignore[assignment]
            stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            return []

        detected = detector.detect(items, context)
        stage.items_out = len(detected)  # type: ignore[assignment]
        stage.status = RunStatus.completed  # type: ignore[assignment]
        stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        return detected

    def _stage_score(
        self, stage: ProcessingStage, items: list[dict[str, Any]],
        scorer_name: str, weights: dict[str, float],
    ) -> list[dict[str, Any]]:
        stage.status = RunStatus.running  # type: ignore[assignment]
        stage.started_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        stage.items_in = len(items)  # type: ignore[assignment]

        scorer = self.registry.get_scorer(scorer_name)
        if not scorer:
            scorer = self.registry.get_scorer("default")
        if not scorer:
            stage.status = RunStatus.failed  # type: ignore[assignment]
            stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            return items

        for item in items:
            item["score"] = scorer.score(item, weights or None)
            item["confidence"] = min(item.get("event_count", 1) / 10.0, 1.0)

        stage.items_out = len(items)  # type: ignore[assignment]
        stage.status = RunStatus.completed  # type: ignore[assignment]
        stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        return items

    def _save_trends(
        self,
        tenant_id: str,
        workspace_id: str | None,
        scored: list[dict[str, Any]],
        run_id: int,
        policy_version_id: int | None,
    ) -> list[Trend]:
        saved: list[Trend] = []
        for item in scored:
            trend = Trend(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source=item.get("source", "unknown"),
                category=item.get("category", "uncategorized"),
                topic=item.get("topic", "unknown"),
                score=item.get("score", 0),
                confidence=item.get("confidence", 0),
                direction=item.get("direction", "rising"),
                event_count=item.get("event_count", 0),
                growth_rate=item.get("growth_rate", 0),
                metadata_json=item,
                run_id=run_id,
            )
            self.db.add(trend)
            self.db.flush()

            # Create decision trace
            trace = DecisionTrace(
                tenant_id=tenant_id,
                entity_type="trend",
                entity_id=trend.id,
                policy_version_id=policy_version_id,
                input_summary_json={"events": item.get("event_count", 0), "source": item.get("source")},
                matched_rules_json=[],
                factor_contributions_json={
                    "event_count": item.get("event_count", 0),
                    "growth_rate": item.get("growth_rate", 0),
                    "total_value": item.get("total_value", 0),
                },
                explanation_text=f"Trend '{item.get('topic')}' detected with {item.get('event_count', 0)} events, score {item.get('score', 0):.1f}",
                explanation_json={
                    "topic": item.get("topic"),
                    "score": item.get("score"),
                    "direction": item.get("direction"),
                    "factors": {
                        "event_count": item.get("event_count", 0),
                        "growth_rate": round(item.get("growth_rate", 0), 2),
                    },
                },
            )
            self.db.add(trace)
            saved.append(trend)

        self.db.flush()
        return saved

    def _stage_recommend(
        self, stage: ProcessingStage, scored: list[dict[str, Any]],
        recommender_name: str, context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        stage.status = RunStatus.running  # type: ignore[assignment]
        stage.started_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        stage.items_in = len(scored)  # type: ignore[assignment]

        recommender = self.registry.get_recommender(recommender_name)
        if not recommender:
            recommender = self.registry.get_recommender("top_n")
        if not recommender:
            stage.status = RunStatus.completed  # type: ignore[assignment]
            stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            return []

        recs = recommender.recommend(scored, context)
        stage.items_out = len(recs)  # type: ignore[assignment]
        stage.status = RunStatus.completed  # type: ignore[assignment]
        stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        return recs

    def _save_recommendations(
        self,
        tenant_id: str,
        workspace_id: str | None,
        recs: list[dict[str, Any]],
        trends: list[Trend],
        run_id: int,
    ) -> list[Recommendation]:
        trend_map = {t.topic: t for t in trends}
        saved: list[Recommendation] = []
        for r in recs:
            topic = r.get("trend_topic", "")
            trend = trend_map.get(topic)
            rec = Recommendation(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                trend_id=trend.id if trend else None,
                category=r.get("category", "uncategorized"),
                title=r.get("title", "Recommendation"),
                body=r.get("body"),
                priority=r.get("priority", "medium"),
                confidence=r.get("confidence", 0),
                run_id=run_id,
            )
            self.db.add(rec)
            self.db.flush()

            # Lineage: recommendation -> trend
            if trend:
                link = SignalLineageLink(
                    tenant_id=tenant_id,
                    from_type="trend",
                    from_id=trend.id,
                    to_type="recommendation",
                    to_id=rec.id,
                    relationship_type="generated",
                )
                self.db.add(link)

            saved.append(rec)

        self.db.flush()
        return saved

    def _stage_alert(
        self,
        stage: ProcessingStage,
        trends: list[Trend],
        tenant_id: str,
        workspace_id: str | None,
        notifier_name: str,
        run_id: int,
    ) -> int:
        stage.status = RunStatus.running  # type: ignore[assignment]
        stage.started_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        stage.items_in = len(trends)  # type: ignore[assignment]

        notifier = self.registry.get_notifier(notifier_name)
        created = 0

        for trend in trends:
            if trend.score >= 50:
                severity = "critical" if trend.score >= 80 else "warning"
                alert = Alert(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    trend_id=trend.id,
                    alert_type="high_score_trend",
                    severity=severity,
                    title=f"High-score trend: {trend.topic}",
                    body=f"Trend '{trend.topic}' reached score {trend.score:.1f}",
                    run_id=run_id,
                )
                self.db.add(alert)
                created += 1

                if notifier:
                    try:
                        notifier.send({
                            "severity": severity,
                            "title": alert.title,
                            "body": alert.body,
                            "tenant_id": tenant_id,
                        })
                    except Exception:
                        logger.warning("Notifier '%s' failed for alert", notifier_name)

        stage.items_out = created  # type: ignore[assignment]
        stage.status = RunStatus.completed  # type: ignore[assignment]
        stage.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        return created

    # ── Backfill / Rebuild ──────────────────────────────────

    def create_backfill(
        self, tenant_id: str, window_start: datetime, window_end: datetime,
        source_filter: str | None = None,
    ) -> BackfillRequest:
        bf = BackfillRequest(
            tenant_id=tenant_id,
            source_filter=source_filter,
            window_start=window_start,
            window_end=window_end,
        )
        self.db.add(bf)
        self.db.flush()

        # Create and run pipeline for backfill
        run = self.run(
            tenant_id,
            source_filter=source_filter,
            run_type="backfill",
            window_start=window_start,
            window_end=window_end,
        )
        bf.run_id = run.id  # type: ignore[assignment]
        bf.status = run.status  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(bf)
        return bf

    def create_rebuild(self, tenant_id: str, target: str = "all") -> RebuildRequest:
        rb = RebuildRequest(
            tenant_id=tenant_id,
            target=target,
        )
        self.db.add(rb)
        self.db.flush()

        run = self.run(
            tenant_id,
            run_type="rebuild",
        )
        rb.run_id = run.id  # type: ignore[assignment]
        rb.status = run.status  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(rb)
        return rb

    def list_runs(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0,
    ) -> list[ProcessingRun]:
        return (
            self.db.query(ProcessingRun)
            .filter(ProcessingRun.tenant_id == tenant_id)
            .order_by(ProcessingRun.created_at.desc())
            .offset(offset).limit(limit).all()
        )

    def get_run(self, run_id: int) -> ProcessingRun | None:
        return self.db.get(ProcessingRun, run_id)

    def get_run_stages(self, run_id: int) -> list[ProcessingStage]:
        return (
            self.db.query(ProcessingStage)
            .filter(ProcessingStage.run_id == run_id)
            .order_by(ProcessingStage.id).all()
        )
