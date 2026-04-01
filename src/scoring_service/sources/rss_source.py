"""RSS feed source provider."""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from scoring_service.sources.base import BaseSourceProvider, SourceEvent, SourceTestResult


class RssSourceProvider(BaseSourceProvider):
    source_type = "rss"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.feeds: list[str] = config.get("feeds", [])
        self.timeout: int = config.get("timeout", 15)

    def validate_config(self) -> list[str]:
        errors = []
        if not self.feeds:
            errors.append("No RSS feeds configured")
        return errors

    async def fetch(self, cursor: str | None = None) -> tuple[list[SourceEvent], str | None]:
        events: list[SourceEvent] = []
        for feed_url in self.feeds:
            try:
                items = await self._fetch_feed(feed_url)
                events.extend(items)
            except Exception:
                continue
        return events, None

    async def _fetch_feed(self, feed_url: str) -> list[SourceEvent]:
        events: list[SourceEvent] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(feed_url, follow_redirects=True)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)

        # Handle both RSS 2.0 and Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.iter("item"):
            title = _text(item, "title")
            link = _text(item, "link")
            desc = _text(item, "description")
            pub_date = _text(item, "pubDate")
            category = _text(item, "category") or "news"
            author = _text(item, "author") or _text(item, "dc:creator") or ""

            published_at = None
            if pub_date:
                try:
                    published_at = parsedate_to_datetime(pub_date)
                except Exception:
                    published_at = datetime.now(timezone.utc)

            ext_id = hashlib.md5((link or title).encode()).hexdigest()[:16]
            events.append(SourceEvent(
                external_id=ext_id,
                source_type="rss",
                source_name=feed_url.split("/")[2] if "/" in feed_url else feed_url,
                title=title or "Untitled",
                body=_strip_html(desc),
                url=link or "",
                author=author,
                category=category.lower(),
                published_at=published_at,
                raw_data={"feed_url": feed_url},
            ))

        # Atom
        for entry in root.findall("atom:entry", ns):
            title = _text_ns(entry, "atom:title", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            summary = _text_ns(entry, "atom:summary", ns) or _text_ns(entry, "atom:content", ns) or ""
            updated = _text_ns(entry, "atom:updated", ns)
            author_el = entry.find("atom:author/atom:name", ns)
            author = author_el.text if author_el is not None else ""

            published_at = None
            if updated:
                try:
                    published_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                except Exception:
                    published_at = datetime.now(timezone.utc)

            ext_id = hashlib.md5((link or title or "").encode()).hexdigest()[:16]
            events.append(SourceEvent(
                external_id=ext_id,
                source_type="rss",
                source_name=feed_url.split("/")[2] if "/" in feed_url else feed_url,
                title=title or "Untitled",
                body=_strip_html(summary),
                url=link,
                author=author,
                category="news",
                published_at=published_at,
                raw_data={"feed_url": feed_url},
            ))

        return events

    async def test_connection(self) -> SourceTestResult:
        if not self.feeds:
            return SourceTestResult(ok=False, message="No feeds configured")
        try:
            events = await self._fetch_feed(self.feeds[0])
            return SourceTestResult(ok=True, message=f"OK, got {len(events)} items from first feed", items_preview=len(events))
        except Exception as e:
            return SourceTestResult(ok=False, message=f"Feed fetch failed: {e}")


def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _text_ns(el: ET.Element, tag: str, ns: dict) -> str:
    child = el.find(tag, ns)
    return (child.text or "").strip() if child is not None else ""


def _strip_html(html: str) -> str:
    import re
    clean = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", clean).strip()[:2000]
