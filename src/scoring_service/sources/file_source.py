"""File/import source provider — JSON and CSV."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any

from scoring_service.sources.base import BaseSourceProvider, SourceEvent, SourceTestResult


class FileSourceProvider(BaseSourceProvider):
    source_type = "file_import"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.file_path: str = config.get("file_path", "")
        self.file_format: str = config.get("format", "json")  # json or csv
        self.content: str = config.get("content", "")  # inline content for API import
        self.mapping: dict[str, str] = config.get("mapping", {})

    def validate_config(self) -> list[str]:
        errors = []
        if not self.file_path and not self.content:
            errors.append("file_path or content is required")
        return errors

    async def fetch(self, cursor: str | None = None) -> tuple[list[SourceEvent], str | None]:
        raw = self.content
        if not raw and self.file_path:
            with open(self.file_path, encoding="utf-8") as f:
                raw = f.read()
        if not raw:
            return [], None

        if self.file_format == "csv":
            return self._parse_csv(raw), None
        return self._parse_json(raw), None

    def _parse_json(self, raw: str) -> list[SourceEvent]:
        data = json.loads(raw)
        items = data if isinstance(data, list) else [data]
        events = []
        m = self.mapping
        for i, item in enumerate(items):
            title = str(item.get(m.get("title", "title"), f"Import {i}"))
            ext_id = str(item.get(m.get("id", "id"), hashlib.md5(title.encode()).hexdigest()[:16]))
            events.append(SourceEvent(
                external_id=f"file_{ext_id}",
                source_type="file_import",
                source_name=self.file_path or "inline",
                title=title[:512],
                body=str(item.get(m.get("body", "body"), ""))[:2000],
                url=str(item.get(m.get("url", "url"), "")),
                category=str(item.get(m.get("category", "category"), "imported")).lower(),
                published_at=datetime.now(timezone.utc),
                raw_data=item if isinstance(item, dict) else {"value": item},
            ))
        return events

    def _parse_csv(self, raw: str) -> list[SourceEvent]:
        reader = csv.DictReader(io.StringIO(raw))
        events = []
        m = self.mapping
        for i, row in enumerate(reader):
            title = row.get(m.get("title", "title"), f"Row {i}")
            ext_id = row.get(m.get("id", "id"), hashlib.md5(str(title).encode()).hexdigest()[:16])
            events.append(SourceEvent(
                external_id=f"file_{ext_id}",
                source_type="file_import",
                source_name=self.file_path or "csv_inline",
                title=str(title)[:512],
                body=str(row.get(m.get("body", "body"), ""))[:2000],
                url=str(row.get(m.get("url", "url"), "")),
                category=str(row.get(m.get("category", "category"), "imported")).lower(),
                published_at=datetime.now(timezone.utc),
                raw_data=dict(row),
            ))
        return events

    async def test_connection(self) -> SourceTestResult:
        try:
            events, _ = await self.fetch()
            return SourceTestResult(ok=True, message=f"OK, parsed {len(events)} items", items_preview=len(events))
        except Exception as e:
            return SourceTestResult(ok=False, message=f"File parse failed: {e}")
