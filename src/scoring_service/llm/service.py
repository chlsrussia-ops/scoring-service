"""LLM service — orchestrates generation, dedup, storage."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import (
    Alert, DigestReport, LlmGeneration, PipelineEvent,
    Recommendation, Trend,
)
from scoring_service.llm.base import LlmProvider, LlmRequest
from scoring_service.llm.mock_provider import MockLlmProvider
from scoring_service.llm.openai_provider import OpenAIProvider
from scoring_service.llm.prompts import TEMPLATES

logger = logging.getLogger("scoring_service")


def create_provider(settings: Settings) -> LlmProvider:
    if settings.llm_provider == "openai" and settings.llm_api_key:
        return OpenAIProvider(settings)
    return MockLlmProvider()


def _input_hash(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class LlmService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.provider = create_provider(settings)

    async def generate_trend_summary(self, trend_id: int, tenant_id: str) -> LlmGeneration:
        trend = self.db.query(Trend).filter(Trend.id == trend_id, Trend.tenant_id == tenant_id).first()
        if not trend:
            raise ValueError(f"Trend {trend_id} not found")

        template = TEMPLATES["trend_summary_v1"]
        input_data = {
            "topic": trend.topic, "category": trend.category, "score": trend.score,
            "confidence": trend.confidence, "direction": trend.direction,
            "growth_rate": trend.growth_rate, "event_count": trend.event_count,
            "source": trend.source, "first_seen": str(trend.first_seen), "last_seen": str(trend.last_seen),
        }

        return await self._generate(
            entity_type="trend", entity_id=trend_id, tenant_id=tenant_id,
            template_name="trend_summary_v1", input_data=input_data,
        )

    async def enhance_recommendation(self, rec_id: int, tenant_id: str) -> LlmGeneration:
        rec = self.db.query(Recommendation).filter(Recommendation.id == rec_id, Recommendation.tenant_id == tenant_id).first()
        if not rec:
            raise ValueError(f"Recommendation {rec_id} not found")

        trend_topic = ""
        trend_score = 0.0
        if rec.trend_id:
            trend = self.db.query(Trend).filter(Trend.id == rec.trend_id).first()
            if trend:
                trend_topic = trend.topic
                trend_score = trend.score

        template = TEMPLATES["recommendation_enhancement_v1"]
        input_data = {
            "title": rec.title, "body": rec.body or "", "priority": rec.priority,
            "category": rec.category, "confidence": rec.confidence,
            "trend_topic": trend_topic, "trend_score": trend_score,
        }

        return await self._generate(
            entity_type="recommendation", entity_id=rec_id, tenant_id=tenant_id,
            template_name="recommendation_enhancement_v1", input_data=input_data,
        )

    async def generate_digest(self, tenant_id: str) -> DigestReport:
        now = datetime.now(timezone.utc)
        trends = self.db.query(Trend).filter(Trend.tenant_id == tenant_id).order_by(Trend.score.desc()).limit(10).all()
        recs = self.db.query(Recommendation).filter(Recommendation.tenant_id == tenant_id).order_by(Recommendation.created_at.desc()).limit(10).all()
        alerts_count = self.db.query(Alert).filter(Alert.tenant_id == tenant_id).count()
        events_count = self.db.query(PipelineEvent).filter(PipelineEvent.tenant_id == tenant_id).count()

        top_trends_text = "\n".join(
            f"- {t.topic} (score: {t.score}, growth: {t.growth_rate}%)" for t in trends[:5]
        ) or "No trends detected yet"
        top_recs_text = "\n".join(
            f"- [{r.priority}] {r.title}" for r in recs[:5]
        ) or "No recommendations yet"

        template = TEMPLATES["executive_digest_v1"]
        input_data = {
            "period": "Last 24 hours",
            "total_events": events_count,
            "trends_count": len(trends),
            "recs_count": len(recs),
            "alerts_count": alerts_count,
            "top_trends": top_trends_text,
            "top_recs": top_recs_text,
        }

        gen = await self._generate(
            entity_type="digest", entity_id=None, tenant_id=tenant_id,
            template_name="executive_digest_v1", input_data=input_data,
        )

        digest = DigestReport(
            tenant_id=tenant_id,
            title=f"Content Intelligence Briefing — {now.strftime(%Y-%m-%d)}",
            summary=gen.output_text,
            top_trends_json=[{"id": t.id, "topic": t.topic, "score": t.score} for t in trends[:5]],
            top_recommendations_json=[{"id": r.id, "title": r.title, "priority": r.priority} for r in recs[:5]],
            key_risks_json=[],
            stats_json={"events": events_count, "trends": len(trends), "recs": len(recs), "alerts": alerts_count},
            llm_generation_id=gen.id,
            period_start=None,
            period_end=now,
        )
        self.db.add(digest)
        self.db.commit()
        self.db.refresh(digest)
        return digest

    async def generate_all_narratives(self, tenant_id: str) -> dict[str, int]:
        """Generate summaries for all trends and recommendations."""
        trends = self.db.query(Trend).filter(Trend.tenant_id == tenant_id).all()
        recs = self.db.query(Recommendation).filter(Recommendation.tenant_id == tenant_id).all()

        trend_count = 0
        for t in trends:
            try:
                await self.generate_trend_summary(t.id, tenant_id)
                trend_count += 1
            except Exception:
                logger.exception("Failed to generate summary for trend %d", t.id)

        rec_count = 0
        for r in recs:
            try:
                await self.enhance_recommendation(r.id, tenant_id)
                rec_count += 1
            except Exception:
                logger.exception("Failed to enhance recommendation %d", r.id)

        return {"trends_summarized": trend_count, "recommendations_enhanced": rec_count}

    async def _generate(
        self, entity_type: str, entity_id: int | None, tenant_id: str,
        template_name: str, input_data: dict[str, Any],
    ) -> LlmGeneration:
        template = TEMPLATES[template_name]
        ih = _input_hash(input_data)

        # Dedup check
        existing = self.db.query(LlmGeneration).filter(
            LlmGeneration.tenant_id == tenant_id,
            LlmGeneration.entity_type == entity_type,
            LlmGeneration.entity_id == entity_id,
            LlmGeneration.prompt_template == template_name,
            LlmGeneration.input_hash == ih,
        ).first()
        if existing:
            return existing

        prompt_text = template.render(**input_data)
        request = LlmRequest(
            prompt=prompt_text,
            system=template.system,
            max_tokens=self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature,
        )

        response = await self.provider.generate(request)

        gen = LlmGeneration(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            prompt_template=template_name,
            prompt_version=template.version,
            provider=response.provider,
            model=response.model,
            input_hash=ih,
            input_snapshot_json=input_data,
            output_text=response.text if not response.error else None,
            output_json=None,
            tokens_used=response.tokens_used,
            error=response.error,
        )
        self.db.add(gen)
        self.db.commit()
        self.db.refresh(gen)
        return gen
