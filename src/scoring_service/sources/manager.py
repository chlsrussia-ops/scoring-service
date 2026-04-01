"""Source manager — orchestrates source providers, sync, and event ingestion."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.db.models import DataSource, PipelineEvent, SourceStatus
from scoring_service.sources.base import BaseSourceProvider, SourceEvent, SourceTestResult
from scoring_service.sources.rss_source import RssSourceProvider
from scoring_service.sources.reddit_source import RedditSourceProvider
from scoring_service.sources.http_api_source import HttpApiSourceProvider
from scoring_service.sources.file_source import FileSourceProvider

logger = logging.getLogger("scoring_service")

PROVIDER_MAP: dict[str, type[BaseSourceProvider]] = {
    "rss": RssSourceProvider,
    "reddit": RedditSourceProvider,
    "http_api": HttpApiSourceProvider,
    "file_import": FileSourceProvider,
}


class SourceManager:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_provider(self, source: DataSource) -> BaseSourceProvider:
        provider_cls = PROVIDER_MAP.get(source.source_type.value if hasattr(source.source_type, "value") else source.source_type)
        if not provider_cls:
            raise ValueError(f"Unknown source type: {source.source_type}")
        return provider_cls(source.config_json or {})

    async def sync_source(self, source: DataSource, tenant_id: str) -> dict[str, Any]:
        """Sync a single source: fetch events, normalize, store as PipelineEvents."""
        provider = self.create_provider(source)

        source.status = SourceStatus.syncing
        self.db.commit()

        try:
            events, cursor = await provider.fetch()
            ingested = 0
            for ev in events:
                # Dedup by external_id
                existing = self.db.query(PipelineEvent).filter(
                    PipelineEvent.tenant_id == tenant_id,
                    PipelineEvent.external_id == ev.external_id,
                ).first()
                if existing:
                    continue

                pe = PipelineEvent(
                    tenant_id=tenant_id,
                    workspace_id=source.workspace_id,
                    source=source.name,
                    event_type=ev.source_type,
                    external_id=ev.external_id,
                    payload_json=ev.model_dump(mode="json"),
                    normalized_json={
                        "title": ev.title,
                        "body": ev.body,
                        "url": ev.url,
                        "category": ev.category,
                        "author": ev.author,
                        "tags": ev.tags,
                        "metrics": ev.metrics,
                        "published_at": ev.published_at.isoformat() if ev.published_at else None,
                    },
                )
                self.db.add(pe)
                ingested += 1

            source.status = SourceStatus.active
            source.last_sync_at = datetime.now(timezone.utc)
            source.items_fetched = source.items_fetched + len(events)
            source.items_normalized = source.items_normalized + ingested
            source.last_error = None
            self.db.commit()

            return {"fetched": len(events), "ingested": ingested, "source": source.name}

        except Exception as e:
            source.status = SourceStatus.error
            source.failure_count = source.failure_count + 1
            source.last_error = str(e)[:1000]
            self.db.commit()
            logger.exception("Source sync failed: %s", source.name)
            return {"fetched": 0, "ingested": 0, "source": source.name, "error": str(e)}

    async def sync_all(self, tenant_id: str) -> list[dict[str, Any]]:
        """Sync all enabled sources for a tenant."""
        sources = self.db.query(DataSource).filter(
            DataSource.tenant_id == tenant_id,
            DataSource.enabled == True,
        ).all()
        results = []
        for src in sources:
            result = await self.sync_source(src, tenant_id)
            results.append(result)
        return results

    async def test_source(self, source: DataSource) -> SourceTestResult:
        provider = self.create_provider(source)
        return await provider.test_connection()
