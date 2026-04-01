"""Demo seed data - 1000+ events, multiple scenarios, realistic content intelligence data."""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any


def _hours_ago(h: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)


def _hash(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:12]


SCENARIO_NEWS_SPIKE = {
    "name": "News / Media Trend Spike",
    "description": "AI content creation tools go viral after major product launch",
    "category": "ai_content_tools",
    "topics": [
        "AI Content Creation Revolution",
        "GPT-5 Launches Content Suite",
        "Adobe Integrates AI Writing Assistant",
        "AI vs Human Content Quality Study",
        "Content Agencies Adopt AI Workflows",
    ],
}

SCENARIO_REDDIT_EXPLOSION = {
    "name": "Reddit Topic Explosion",
    "description": "Short-form video strategy discussion explodes across subreddits",
    "category": "short_form_video",
    "topics": [
        "TikTok Algorithm Shift Impacts Brands",
        "YouTube Shorts Monetization Doubles",
        "Instagram Reels Outperforms Feed Posts",
        "Short-Form Video Production Tips",
        "Brand Case Study: 10M Views in 48h",
    ],
}

SCENARIO_ANOMALY = {
    "name": "Category Anomaly / Emerging Theme",
    "description": "Creator economy + AI intersection emerges as unexpected theme",
    "category": "creator_economy_ai",
    "topics": [
        "AI-Powered Creator Tools Funding Surge",
        "Creator Burnout Solution: AI Assistants",
        "Niche Content Discovery via ML",
        "Automated Thumbnail/Title Testing",
        "Micro-Influencer AI Matching Platforms",
    ],
}

NOISE_CATEGORIES = [
    ("seo_updates", ["Google Core Update Analysis", "Link Building Strategies 2026", "Technical SEO Audit Findings"]),
    ("email_marketing", ["Newsletter Growth Tactics", "Email Deliverability Changes", "Personalization Engine Results"]),
    ("podcast_trends", ["Podcast Discovery Algorithms", "Audio Content Engagement Study", "Podcast Ad Revenue Growth"]),
    ("ecommerce_content", ["Product Content Optimization", "Marketplace Listing Best Practices", "UGC for E-commerce"]),
    ("brand_safety", ["Content Moderation Challenges", "Brand Safety Score Tools", "Misinformation Detection Advances"]),
]


def generate_events(count: int = 1200) -> list[dict[str, Any]]:
    """Generate diverse demo events across scenarios and noise."""
    rng = random.Random(42)
    events: list[dict[str, Any]] = []
    scenarios = [SCENARIO_NEWS_SPIKE, SCENARIO_REDDIT_EXPLOSION, SCENARIO_ANOMALY]

    for scenario in scenarios:
        for topic in scenario["topics"]:
            base_volume = rng.randint(15, 40)
            for i in range(base_volume):
                hours = rng.randint(0, 72)
                source_type = rng.choice(["rss", "reddit", "http_api"])
                source_name = rng.choice(["TechCrunch", "The Verge", "r/marketing", "r/technology", "r/artificial", "ContentMarketing API", "MediaWatch"])
                variation = rng.choice(["", " - Analysis", " - Update", " - Deep Dive", " - Expert Take"])
                ev_title = topic + variation
                events.append({
                    "external_id": "demo_" + _hash(topic + "_" + str(i)),
                    "source_type": source_type,
                    "source_name": source_name,
                    "title": ev_title,
                    "body": _gen_body(topic, scenario["category"], rng),
                    "url": "https://example.com/article/" + _hash(topic) + "_" + str(i),
                    "author": "author_" + str(rng.randint(1, 200)),
                    "category": scenario["category"],
                    "tags": [scenario["category"], source_type],
                    "published_at": _hours_ago(hours).isoformat(),
                    "metrics": {
                        "upvotes": float(rng.randint(10, 2000)),
                        "comments": float(rng.randint(5, 300)),
                        "shares": float(rng.randint(2, 500)),
                        "engagement_score": round(rng.uniform(0.3, 0.95), 2),
                    },
                    "scenario": scenario["name"],
                })

    for cat, topics in NOISE_CATEGORIES:
        for topic in topics:
            for i in range(rng.randint(30, 50)):
                hours = rng.randint(0, 168)
                events.append({
                    "external_id": "demo_" + _hash(topic + "_" + str(i) + "_noise"),
                    "source_type": rng.choice(["rss", "reddit", "http_api", "file_import"]),
                    "source_name": rng.choice(["MarketingBlog", "SEO Weekly", "r/marketing", "IndustryDigest"]),
                    "title": topic + " (#" + str(i) + ")",
                    "body": "Regular update on " + topic.lower() + ". Standard industry coverage with moderate engagement.",
                    "url": "https://example.com/content/" + _hash(topic) + "_" + str(i),
                    "author": "writer_" + str(rng.randint(1, 100)),
                    "category": cat,
                    "tags": [cat],
                    "published_at": _hours_ago(hours).isoformat(),
                    "metrics": {
                        "upvotes": float(rng.randint(1, 100)),
                        "comments": float(rng.randint(0, 30)),
                        "shares": float(rng.randint(0, 20)),
                        "engagement_score": round(rng.uniform(0.05, 0.4), 2),
                    },
                    "scenario": "noise",
                })

    while len(events) < count:
        i = len(events)
        events.append({
            "external_id": "demo_fill_" + _hash(str(i)),
            "source_type": rng.choice(["rss", "reddit"]),
            "source_name": rng.choice(["MiscFeed", "r/general", "IndustryNews"]),
            "title": "Industry Update #" + str(i),
            "body": "General industry update with minor relevance.",
            "url": "https://example.com/misc/" + str(i),
            "author": "bot_" + str(i),
            "category": rng.choice(["general", "industry", "misc"]),
            "tags": ["filler"],
            "published_at": _hours_ago(rng.randint(0, 336)).isoformat(),
            "metrics": {"engagement_score": round(rng.uniform(0.01, 0.2), 2)},
            "scenario": "noise",
        })

    rng.shuffle(events)
    return events[:count]


def generate_trends() -> list[dict[str, Any]]:
    """Generate demo trends from scenarios."""
    rng = random.Random(42)
    trends = []
    for scenario in [SCENARIO_NEWS_SPIKE, SCENARIO_REDDIT_EXPLOSION, SCENARIO_ANOMALY]:
        for topic in scenario["topics"]:
            trends.append({
                "source": rng.choice(["TechCrunch", "r/marketing", "r/technology", "ContentAPI"]),
                "category": scenario["category"],
                "topic": topic,
                "score": round(rng.uniform(60, 98), 1),
                "confidence": round(rng.uniform(0.65, 0.95), 2),
                "direction": rng.choice(["rising", "rising", "rising", "accelerating"]),
                "event_count": rng.randint(15, 120),
                "growth_rate": round(rng.uniform(15, 200), 1),
                "scenario": scenario["name"],
            })

    for cat, topics in NOISE_CATEGORIES[:3]:
        for topic in topics[:2]:
            trends.append({
                "source": "mixed",
                "category": cat,
                "topic": topic,
                "score": round(rng.uniform(10, 45), 1),
                "confidence": round(rng.uniform(0.2, 0.55), 2),
                "direction": rng.choice(["stable", "declining", "rising"]),
                "event_count": rng.randint(5, 30),
                "growth_rate": round(rng.uniform(-5, 15), 1),
                "scenario": "noise",
            })
    return trends


def generate_recommendations(trends: list[dict]) -> list[dict[str, Any]]:
    """Generate demo recommendations linked to trend data."""
    rng = random.Random(42)
    templates = [
        ("Publish fast-follow content on {topic}", "Create timely content targeting '{topic}' while momentum is strong. This trend shows {growth}% growth.", "high"),
        ("Escalate {topic} to editorial team", "Brief the editorial team on '{topic}'. The trend confidence is {conf} and growing.", "high"),
        ("Monitor {source} for sustained growth on {topic}", "Set up alerts for '{topic}' on {source}. Confirm the signal holds before committing resources.", "medium"),
        ("Investigate discussion around {topic}", "The conversation around '{topic}' shows mixed signals. Assess sentiment before engaging.", "medium"),
        ("Prepare campaign angle for {category}", "Emerging category '{category}' shows opportunity for brand positioning. Research competitor activity.", "low"),
    ]
    recs = []
    for trend in trends:
        if trend["score"] < 40:
            continue
        tmpl = rng.choice(templates)
        recs.append({
            "category": trend["category"],
            "title": tmpl[0].format(topic=trend["topic"], source=trend["source"], category=trend["category"]),
            "body": tmpl[1].format(topic=trend["topic"], source=trend["source"], category=trend["category"], growth=trend["growth_rate"], conf=trend["confidence"]),
            "priority": tmpl[2],
            "confidence": trend["confidence"],
        })
    return recs


def generate_alerts(trends: list[dict]) -> list[dict[str, Any]]:
    """Generate demo alerts for high-scoring trends."""
    rng = random.Random(42)
    alerts = []
    for trend in trends:
        if trend["score"] < 70:
            continue
        alerts.append({
            "alert_type": rng.choice(["trend_spike", "growth_anomaly", "volume_threshold"]),
            "severity": "high" if trend["score"] > 85 else "medium",
            "title": "Trending: " + trend["topic"],
            "body": "Trend '" + trend["topic"] + "' in " + trend["category"] + " has score " + str(trend["score"]) + " with " + str(trend["growth_rate"]) + "% growth.",
            "status": rng.choice(["open", "open", "acknowledged"]),
        })
    return alerts


def generate_demo_sources() -> list[dict[str, Any]]:
    """Pre-configured demo data sources."""
    return [
        {
            "name": "TechCrunch RSS",
            "source_type": "rss",
            "config_json": {"feeds": ["https://techcrunch.com/feed/"], "timeout": 15},
        },
        {
            "name": "Reddit Marketing",
            "source_type": "reddit",
            "config_json": {"subreddits": ["marketing", "content_marketing", "socialmedia"], "mock_mode": True, "limit": 50},
        },
        {
            "name": "Reddit Technology",
            "source_type": "reddit",
            "config_json": {"subreddits": ["technology", "artificial", "MachineLearning"], "mock_mode": True, "limit": 50},
        },
        {
            "name": "HackerNews API",
            "source_type": "http_api",
            "config_json": {
                "endpoint": "https://hacker-news.firebaseio.com/v0/topstories.json",
                "items_path": "",
                "mapping": {"title": "title", "url": "url"},
                "timeout": 15,
            },
        },
    ]


def _gen_body(topic: str, category: str, rng: random.Random) -> str:
    intros = [
        "A significant development in " + category.replace("_", " ") + ": " + topic.lower() + ".",
        "The latest analysis of " + topic.lower() + " reveals interesting patterns.",
        "Industry experts are discussing " + topic.lower() + " as a potential game-changer.",
        "New data shows " + topic.lower() + " is gaining traction across platforms.",
    ]
    details = [
        "Engagement metrics are up significantly compared to baseline.",
        "Multiple independent sources confirm the trend direction.",
        "Content teams across the industry are starting to respond.",
        "Early adopters report strong performance metrics.",
        "This aligns with broader shifts in content consumption patterns.",
    ]
    return rng.choice(intros) + " " + rng.choice(details) + " " + rng.choice(details)
