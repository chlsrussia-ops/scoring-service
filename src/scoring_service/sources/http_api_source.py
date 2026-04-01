"""Generic HTTP JSON API source provider."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import httpx

from scoring_service.sources.base import BaseSourceProvider, SourceEvent, SourceTestResult


def _extract_jsonpath(data: Any, path: str) -> Any:
    """Simple dot-notation JSON path extraction."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current


class HttpApiSourceProvider(BaseSourceProvider):
    source_type = "http_api"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.endpoint: str = config.get("endpoint", "")
        self.headers: dict[str, str] = config.get("headers", {})
        self.auth_token: str = config.get("auth_token", "")
        self.method: str = config.get("method", "GET").upper()
        self.items_path: str = config.get("items_path", "")  # jsonpath to array of items
        self.mapping: dict[str, str] = config.get("mapping", {})  # field -> jsonpath
        self.timeout: int = config.get("timeout", 15)

    def validate_config(self) -> list[str]:
        errors = []
        if not self.endpoint:
            errors.append("endpoint is required")
        return errors

    async def fetch(self, cursor: str | None = None) -> tuple[list[SourceEvent], str | None]:
        events: list[SourceEvent] = []
        headers = dict(self.headers)
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if self.method == "POST":
                resp = await client.post(self.endpoint, headers=headers)
            else:
                resp = await client.get(self.endpoint, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()

        items = data
        if self.items_path:
            items = _extract_jsonpath(data, self.items_path)
        if not isinstance(items, list):
            items = [items] if items else []

        mapping = self.mapping or {}
        for i, item in enumerate(items):
            title = str(_extract_jsonpath(item, mapping.get("title", "title")) or f"Item {i}")
            body = str(_extract_jsonpath(item, mapping.get("body", "body")) or "")
            url = str(_extract_jsonpath(item, mapping.get("url", "url")) or "")
            author = str(_extract_jsonpath(item, mapping.get("author", "author")) or "")
            category = str(_extract_jsonpath(item, mapping.get("category", "category")) or "general")

            ext_id = str(_extract_jsonpath(item, mapping.get("id", "id")) or hashlib.md5(title.encode()).hexdigest()[:16])

            events.append(SourceEvent(
                external_id=f"api_{ext_id}",
                source_type="http_api",
                source_name=self.endpoint.split("/")[2] if "/" in self.endpoint else "api",
                title=title[:512],
                body=body[:2000],
                url=url,
                author=author,
                category=category.lower(),
                published_at=datetime.now(timezone.utc),
                raw_data={"source": self.endpoint, "original": item},
            ))

        return events, None

    async def test_connection(self) -> SourceTestResult:
        if not self.endpoint:
            return SourceTestResult(ok=False, message="No endpoint configured")
        try:
            events, _ = await self.fetch()
            return SourceTestResult(ok=True, message=f"OK, got {len(events)} items", items_preview=len(events))
        except Exception as e:
            return SourceTestResult(ok=False, message=f"API fetch failed: {e}")
