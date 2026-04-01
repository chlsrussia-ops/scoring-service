"""Reddit source provider with auth fallback to public JSON API."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import httpx

from scoring_service.sources.base import BaseSourceProvider, SourceEvent, SourceTestResult


class RedditSourceProvider(BaseSourceProvider):
    source_type = "reddit"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.subreddits: list[str] = config.get("subreddits", ["technology"])
        self.client_id: str = config.get("client_id", "")
        self.client_secret: str = config.get("client_secret", "")
        self.user_agent: str = config.get("user_agent", "TrendIntel/1.0")
        self.limit: int = config.get("limit", 50)
        self.mock_mode: bool = config.get("mock_mode", False)
        self.timeout: int = config.get("timeout", 15)

    def validate_config(self) -> list[str]:
        errors = []
        if not self.subreddits:
            errors.append("No subreddits configured")
        return errors

    async def fetch(self, cursor: str | None = None) -> tuple[list[SourceEvent], str | None]:
        if self.mock_mode:
            return self._generate_mock_data(), None

        events: list[SourceEvent] = []
        for sub in self.subreddits:
            try:
                items = await self._fetch_subreddit(sub)
                events.extend(items)
            except Exception:
                continue
        return events, None

    async def _fetch_subreddit(self, subreddit: str) -> list[SourceEvent]:
        events: list[SourceEvent] = []
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={self.limit}"
        headers = {"User-Agent": self.user_agent}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            ext_id = post.get("id", hashlib.md5(title.encode()).hexdigest()[:16])
            created_utc = post.get("created_utc", 0)

            events.append(SourceEvent(
                external_id=f"reddit_{ext_id}",
                source_type="reddit",
                source_name=f"r/{subreddit}",
                title=title,
                body=(post.get("selftext", "") or "")[:2000],
                url=f"https://reddit.com{post.get(permalink, )}",
                author=post.get("author", ""),
                category=subreddit.lower(),
                tags=[f.get("e", "") for f in post.get("link_flair_richtext", []) if f.get("t")],
                published_at=datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else None,
                metrics={
                    "upvotes": float(post.get("ups", 0)),
                    "comments": float(post.get("num_comments", 0)),
                    "upvote_ratio": float(post.get("upvote_ratio", 0)),
                    "score": float(post.get("score", 0)),
                },
                raw_data={"subreddit": subreddit, "post_id": ext_id},
            ))

        return events

    def _generate_mock_data(self) -> list[SourceEvent]:
        """Generate realistic mock Reddit data for demo."""
        import random
        topics = [
            ("AI-powered content creation tools are changing the game", "artificial", "Technology"),
            ("New TikTok algorithm update impacts content creators", "marketing", "Social Media"),
            ("Short-form video dominates Q1 2026 marketing budgets", "marketing", "Marketing"),
            ("GPT-5 capabilities leaked: implications for content teams", "artificial", "AI"),
            ("Reddit IPO one year later: community-driven content wins", "technology", "Business"),
            ("YouTube Shorts surpasses 100B daily views", "technology", "Social Media"),
            ("Brands shifting 40% budgets to creator economy", "marketing", "Marketing"),
            ("AI-generated product reviews raising trust concerns", "technology", "Ethics"),
            ("Instagram launches AI content assistant for businesses", "marketing", "Social Media"),
            ("Content personalization ROI study: 340% improvement", "marketing", "Research"),
            ("Voice search optimization becomes critical for SEO", "technology", "SEO"),
            ("Gen-Z content consumption habits reshape media strategy", "marketing", "Demographics"),
            ("Podcast advertising revenue hits $4B milestone", "business", "Audio"),
            ("Machine learning for real-time content optimization", "artificial", "Technology"),
            ("E-commerce live streaming trend expands to Western markets", "business", "E-commerce"),
        ]
        events = []
        for title, sub, cat in topics:
            ext_id = hashlib.md5(title.encode()).hexdigest()[:16]
            events.append(SourceEvent(
                external_id=f"reddit_{ext_id}",
                source_type="reddit",
                source_name=f"r/{sub}",
                title=title,
                body=f"Discussion about: {title}. This trend shows significant momentum in the content/media space.",
                url=f"https://reddit.com/r/{sub}/comments/{ext_id}",
                author=f"user_{random.randint(1000,9999)}",
                category=cat.lower(),
                tags=[cat.lower(), sub],
                published_at=datetime.now(timezone.utc),
                metrics={
                    "upvotes": float(random.randint(50, 5000)),
                    "comments": float(random.randint(10, 500)),
                    "upvote_ratio": round(random.uniform(0.7, 0.99), 2),
                    "score": float(random.randint(100, 8000)),
                },
                raw_data={"subreddit": sub, "mock": True},
            ))
        return events

    async def test_connection(self) -> SourceTestResult:
        if self.mock_mode:
            return SourceTestResult(ok=True, message="Mock mode active, 15 items available", items_preview=15)
        try:
            events = await self._fetch_subreddit(self.subreddits[0])
            return SourceTestResult(ok=True, message=f"OK, got {len(events)} posts from r/{self.subreddits[0]}", items_preview=len(events))
        except Exception as e:
            return SourceTestResult(ok=False, message=f"Reddit fetch failed: {e}. Enable mock_mode for demo.")
